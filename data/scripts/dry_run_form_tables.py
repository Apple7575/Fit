"""서식 표 파서 dry run. DB 에 쓰지 않고 기업별 서식 표 수·행 수·열 밀림 비율과 표본 행을 JSON 으로 남긴다.

    python data/scripts/dry_run_form_tables.py --dart-archive outputs/dart-local-extracted --corp-code 01021666 ... --out outputs/form-tables-dry-run.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataclasses import replace  # noqa: E402

from pipeline.business_report.doc import Document  # noqa: E402
from pipeline.patterns import patterns as default_patterns  # noqa: E402
from pipeline.business_report.form_tables import FORM_SPECS, form_tables  # noqa: E402
from pipeline.raw_sources.dart_archive import DartArchive  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dart-archive", type=Path, required=True)
    parser.add_argument("--corp-code", action="append", required=True)
    parser.add_argument("--latest-only", action="store_true", help="기업별 최신 보고서 하나만")
    parser.add_argument("--samples", type=int, default=3, help="서식별로 남길 표본 행 수")
    parser.add_argument("--include-tu", action="store_true", help="DART TU(단위 코드) 셀도 표 셀로 읽는다. 기본 설정(patterns.yaml)은 TD·TE·TH 만 읽는다")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    base = default_patterns()
    pats = replace(base, rnd=replace(base.rnd, cell_tags=(*base.rnd.cell_tags, "TU"))) if args.include_tu else base

    labels = {spec.code: spec.label for spec in FORM_SPECS}
    report: dict = {"companies": {}, "by_form": {}}
    totals: Counter = Counter()
    misaligned: Counter = Counter()
    samples: dict[str, list] = {}
    with DartArchive(args.dart_archive) as archive:
        for corp_code in dict.fromkeys(args.corp_code):
            refs = sorted(archive.documents(corp_code), key=lambda r: r.rcept_no)
            if args.latest_only and refs:
                refs = refs[-1:]
            company = {"documents": len(refs), "forms": {}}
            for ref in refs:
                document = Document.from_bytes(archive.read(ref), rcept_no=ref.rcept_no, p=pats)
                for form in form_tables(document, report_year=ref.year):
                    entry = company["forms"].setdefault(form.form_code, {"tables": 0, "rows": 0, "numbers": 0, "misaligned": 0, "reasons": []})
                    entry["tables"] += 1
                    entry["rows"] += len(form.rows)
                    entry["numbers"] += sum(1 for r in form.rows if r.parse_status == "NUMBER")
                    totals[form.form_code] += 1
                    if form.misaligned_reason:
                        entry["misaligned"] += 1
                        entry["reasons"].append(form.misaligned_reason)
                        misaligned[form.form_code] += 1
                    bucket = samples.setdefault(form.form_code, [])
                    if len(bucket) < args.samples and form.rows:
                        bucket.append({
                            "corp_code": corp_code, "rcept_no": ref.rcept_no, "section": form.section_title,
                            "header": form.header, "unit": form.unit, "entity_scope": form.entity_scope,
                            "status": form.status, "reason": form.misaligned_reason,
                            "rows": [
                                {"labels": r.row_labels, "column": r.column_key, "text": r.value_text, "num": r.value_num, "year": r.fiscal_year, "status": r.parse_status}
                                for r in form.rows[:8]
                            ],
                        })
            report["companies"][corp_code] = company
            print(f"[{corp_code}] docs={len(refs)} " + " ".join(f"{labels.get(k, k)}={v['tables']}({v['misaligned']}밀림)" for k, v in company["forms"].items()), file=sys.stderr)
    report["by_form"] = {code: {"label": labels.get(code, code), "tables": totals[code], "misaligned": misaligned[code]} for code in totals}
    report["samples"] = samples
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"saved: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

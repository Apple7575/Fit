"""기업 리포트를 동기적으로 다시 만들고 JSON 과 요약을 남긴다.

    python -m ai.scripts.regenerate_company_reports --corp-code 01350869 ... --out <폴더>

환경변수는 ai/company_analysis/api.py 와 같다(서비스 DB, 청크 DB, Qwen, 임베딩). 서술 생성기가 정형 표
(company_table_row)를 쓰는지 확인하기 위해 섹션별로 인용 근거의 종류(정형 표 / 원문 청크 / 확정 지표)와
경고를 요약한다. 결과 리포트는 서비스 DB 저장소에도 그대로 저장된다.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ai.company_analysis.api import _connect_factory, build_enrichers, resolve_database_url  # noqa: E402
from ai.company_analysis.repository import PostgresCompanyFactsRepository  # noqa: E402
from ai.company_analysis.service import CompanyAnalysisService  # noqa: E402
from ai.company_analysis.store import PostgresReportStore  # noqa: E402


def summarize(report: dict) -> dict:
    sections = []
    for section in report.get("sections", []):
        items = 0
        sources: Counter = Counter()
        for block in section.get("blocks", []):
            entries = block.get("items") or []
            if block.get("kind") == "swot":
                entries = [i for q in ("strengths", "weaknesses", "opportunities", "threats") for i in (block.get(q) or {}).get("items", [])]
            if block.get("kind") == "text" and block.get("text"):
                entries = [block]
            for item in entries:
                items += 1
                for citation in item.get("citations") or []:
                    sources[citation.get("source_type", "?")] += 1
        sections.append({"type": section.get("type"), "status": section.get("status"), "items": items, "citation_sources": dict(sources)})
    return {"stage": report.get("stage"), "sections": sections, "warnings": report.get("warnings", [])}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corp-code", action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    connect = _connect_factory(resolve_database_url())
    service = CompanyAnalysisService(
        repository=PostgresCompanyFactsRepository(connect), store=PostgresReportStore(connect), enrichers=build_enrichers(), executor=None,
    )
    results = {}
    for corp_code in dict.fromkeys(args.corp_code):
        started = time.perf_counter()
        status = service.generate(corp_code, force=True)
        stored = service.get_or_generate(corp_code)
        report = stored.report.model_dump(mode="json") if stored.report else {}
        elapsed = round(time.perf_counter() - started, 1)
        (args.out / f"{corp_code}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        summary = {"status": status.status, "elapsed_s": elapsed, **summarize(report)}
        results[corp_code] = summary
        print(f"[{corp_code}] {status.status} {elapsed}s " + " ".join(f"{s['type']}={s['status']}/{s['items']}{s['citation_sources']}" for s in summary["sections"]), file=sys.stderr, flush=True)
        for warning in summary["warnings"]:
            print(f"    ! {warning}", file=sys.stderr, flush=True)
    (args.out / "summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"saved: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

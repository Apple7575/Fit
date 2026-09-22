"""기업별 사업보고서 청크 스테이징을 XML 재파싱 없이 DB에 적재한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Callable, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.rag_corpus.load import build_business_report_records, replace_business_reports  # noqa: E402
from pipeline.raw_sources.staging import read_staged_records  # noqa: E402


ConnectionFactory = Callable[[], object]


def connect():
    from pipeline.db import connect as database_connect

    return database_connect()


def load_staging(
    conn_factory: ConnectionFactory, staging_dir: Path, *, corp_codes: list[str] | None,
    dry_run: bool,
) -> dict[str, object]:
    summaries = {
        path.name.removesuffix(".summary.json"): path
        for path in staging_dir.glob("*.summary.json")
    }
    selected = sorted(set(corp_codes)) if corp_codes else sorted(summaries)
    missing = [code for code in selected if code not in summaries]
    if missing:
        raise ValueError(f"스테이징 요약이 없는 기업입니다: {', '.join(missing)}")
    companies: dict[str, dict[str, object]] = {}
    record_count = 0
    warnings: list[dict[str, object]] = []
    for corp_code in selected:
        summary = json.loads(summaries[corp_code].read_text(encoding="utf-8"))
        records = read_staged_records(Path(summary["records_path"]))
        result = build_business_report_records(corp_code, records)
        if len(result.records) != int(summary["record_count"]):
            raise ValueError(f"스테이징 레코드 수가 요약과 다릅니다: {corp_code}")
        if not dry_run:
            with conn_factory() as conn:
                replace_business_reports(conn, corp_code, result.records)
        company_warnings = list(summary.get("failures") or [])
        warnings.extend({**warning, "corp_code": corp_code} for warning in company_warnings)
        companies[corp_code] = {
            "record_count": len(result.records),
            "write_status": "validated" if dry_run else "replaced",
            "warning_count": len(company_warnings),
        }
        record_count += len(result.records)
    return {
        "company_count": len(selected), "record_count": record_count,
        "companies": companies, "warnings": warnings,
    }


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RAG 코퍼스 스테이징 적재")
    parser.add_argument("--staging-dir", type=Path, required=True)
    parser.add_argument("--corp-code", action="append")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    try:
        summary = load_staging(
            connect, args.staging_dir, corp_codes=args.corp_code, dry_run=args.dry_run,
        )
    except Exception as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False))
        return 1
    payload = {"status": "success", **summary}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8",
        )
    print(json.dumps({
        "status": "success", "company_count": summary["company_count"],
        "record_count": summary["record_count"], "warning_count": len(summary["warnings"]),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

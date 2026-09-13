"""기업별 정본 데이터를 PostgreSQL RAG 코퍼스로 결정적으로 재구축한다.

    python data/scripts/build_rag_corpus.py --dry-run
    python data/scripts/build_rag_corpus.py --corp-code 00126380
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, ContextManager, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.rag_corpus.load import BuildResult, build_company_records, replace_company  # noqa: E402
from pipeline.rag_corpus.source import load_company_source_rows  # noqa: E402


ConnectionFactory = Callable[[], ContextManager[object]]


def connect():
    """실행 시점에만 DB 드라이버를 가져와 변환 단위 테스트를 독립시킨다."""
    from pipeline.db import connect as database_connect

    return database_connect()


@dataclass
class BuildSummary:
    """JSON 출력에 쓰는 기업별·전체 구축 계측값이다."""

    started_at: float = field(default_factory=time.monotonic)
    companies: dict[str, dict[str, object]] = field(default_factory=dict)
    input_counts: Counter[str] = field(default_factory=Counter)
    excluded_counts: Counter[str] = field(default_factory=Counter)
    record_count: int = 0

    def add(self, corp_code: str, result: BuildResult) -> None:
        records = len(result.records)
        self.companies[corp_code] = {
            "record_count": records,
            "input_counts": dict(sorted(result.input_counts.items())),
            "excluded_counts": dict(sorted(result.excluded_counts.items())),
        }
        self.input_counts.update(result.input_counts)
        self.excluded_counts.update(result.excluded_counts)
        self.record_count += records

    def as_dict(self) -> dict[str, object]:
        return {
            "company_count": len(self.companies),
            "record_count": self.record_count,
            "input_counts": dict(sorted(self.input_counts.items())),
            "excluded_counts": dict(sorted(self.excluded_counts.items())),
            "companies": dict(sorted(self.companies.items())),
            "elapsed_ms": int((time.monotonic() - self.started_at) * 1000),
        }


def resolve_company_codes(conn_factory: ConnectionFactory, corp_codes: list[str] | None) -> list[str]:
    """기업 마스터에서 전수 목록을 읽고, 지정 코드는 적재 전 모두 검증한다."""
    with conn_factory() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT corp_code FROM company ORDER BY corp_code")
            known = {row[0] for row in cur.fetchall()}

    if corp_codes is None:
        return sorted(known)

    selected = list(dict.fromkeys(corp_codes))
    unknown = [corp_code for corp_code in selected if corp_code not in known]
    if unknown:
        raise ValueError(f"기업을 찾을 수 없습니다: {unknown[0]}")
    return selected


def run(conn_factory: ConnectionFactory, corp_codes: list[str] | None, *, dry_run: bool) -> dict[str, object]:
    """기업별 독립 트랜잭션으로 코퍼스를 교체하고 요약값을 반환한다."""
    selected = resolve_company_codes(conn_factory, corp_codes)
    summary = BuildSummary()
    for corp_code in selected:
        with conn_factory() as conn:
            rows = load_company_source_rows(conn, corp_code)
            result = build_company_records(rows)
            if not dry_run:
                replace_company(conn, corp_code, result.records)
            summary.add(corp_code, result)
    return summary.as_dict()


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="기업별 RAG 코퍼스 재구축")
    parser.add_argument("--corp-code", action="append", help="재구축할 8자리 기업 코드 (여러 번 지정 가능)")
    parser.add_argument("--dry-run", action="store_true", help="삭제·삽입 없이 입력과 변환 결과만 집계")
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    try:
        summary = run(connect, args.corp_code, dry_run=args.dry_run)
    except Exception as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "success", **summary}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

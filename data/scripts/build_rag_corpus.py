"""기업별 정본 데이터를 PostgreSQL RAG 코퍼스로 결정적으로 재구축한다.

    python data/scripts/build_rag_corpus.py --dry-run
    python data/scripts/build_rag_corpus.py --corp-code 00126380
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, ContextManager, Iterable, Protocol

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.rag_corpus.load import BuildResult, build_company_records, replace_company  # noqa: E402
from pipeline.rag_corpus.source import load_company_source_rows  # noqa: E402
from pipeline.rag_corpus.models import EvidenceRecord  # noqa: E402
from pipeline.raw_sources.business_report import BusinessReportSource  # noqa: E402
from pipeline.raw_sources.dart_archive import DartArchive  # noqa: E402
from pipeline.raw_sources.models import EvidenceBatch  # noqa: E402


ConnectionFactory = Callable[[], ContextManager[object]]


class ExternalEvidenceProvider(Protocol):
    def batch(self, corp_code: str) -> EvidenceBatch: ...

    def inventory(self) -> dict[str, object]: ...


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
    failures: list[dict[str, object]] = field(default_factory=list)

    def add(
        self, corp_code: str, result: BuildResult, *, failures: list[dict[str, object]], write_status: str,
    ) -> None:
        records = len(result.records)
        self.companies[corp_code] = {
            "record_count": records,
            "input_counts": dict(sorted(result.input_counts.items())),
            "excluded_counts": dict(sorted(result.excluded_counts.items())),
            "write_status": write_status,
        }
        if failures:
            self.companies[corp_code]["failures"] = failures
            self.failures.extend(failures)
        self.input_counts.update(result.input_counts)
        self.excluded_counts.update(result.excluded_counts)
        self.record_count += records

    def add_external(self, corp_code: str, batch: EvidenceBatch) -> None:
        """사업보고서 배치의 원문·청크 계측값을 기업 및 전체 합계에 반영한다."""
        input_counts = Counter(batch.input_counts)
        input_counts.update(
            f"business_report_{record.metadata['content_type'].lower()}_chunks"
            for record in batch.records
            if getattr(record, "source_type", None) == "DART_BUSINESS_REPORT"
            and getattr(record, "metadata", {}).get("content_type") in ("TEXT", "TABLE")
        )
        company = self.companies[corp_code]
        for key, counts in (
            ("input_counts", input_counts),
            ("excluded_counts", batch.excluded_counts),
        ):
            total = Counter(company[key])
            total.update(counts)
            company[key] = dict(sorted(total.items()))
            external = Counter(company.get(f"external_{key}", {}))
            external.update(counts)
            company[f"external_{key}"] = dict(sorted(external.items()))
        self.input_counts.update(input_counts)
        self.excluded_counts.update(batch.excluded_counts)

    def as_dict(self) -> dict[str, object]:
        return {
            "company_count": len(self.companies),
            "record_count": self.record_count,
            "input_counts": dict(sorted(self.input_counts.items())),
            "excluded_counts": dict(sorted(self.excluded_counts.items())),
            "companies": dict(sorted(self.companies.items())),
            "failures": self.failures,
            "elapsed_ms": int((time.monotonic() - self.started_at) * 1000),
        }


def add_embedding_estimate(summary: dict[str, object], dimension: int) -> dict[str, object]:
    if dimension <= 0:
        raise ValueError("embedding_dimension은 양수여야 합니다")
    return {
        **summary,
        "embedding_dimension": dimension,
        "estimated_embedding_bytes": int(summary["record_count"]) * dimension * 4,
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


def run(
    conn_factory: ConnectionFactory, corp_codes: list[str] | None, *, dry_run: bool,
    external_providers: Iterable[ExternalEvidenceProvider] = (),
    embedding_dimension: int = 1024,
) -> dict[str, object]:
    """기업별 독립 트랜잭션으로 코퍼스를 교체하고 요약값을 반환한다."""
    if embedding_dimension <= 0:
        raise ValueError("embedding_dimension은 양수여야 합니다")
    selected = resolve_company_codes(conn_factory, corp_codes)
    providers = list(external_providers)
    summary = BuildSummary()
    for corp_code in selected:
        with conn_factory() as conn:
            rows = load_company_source_rows(conn, corp_code)
            batches = [(provider.__class__.__name__, provider.batch(corp_code)) for provider in providers]
            external = [record for _, batch in batches for record in batch.records]
            failures = [
                {**failure, "corp_code": corp_code, "provider": provider}
                for provider, batch in batches for failure in batch.failures
            ]
            result = build_company_records(rows, external_records=external) if providers else build_company_records(rows)
            if not dry_run and not failures:
                replace_company(conn, corp_code, result.records)
            summary.add(
                corp_code, result, failures=failures,
                write_status="dry_run" if dry_run else "skipped_due_to_source_failure" if failures else "replaced",
            )
            for _, batch in batches:
                summary.add_external(corp_code, batch)
    result = summary.as_dict()
    result["companies"] = {
        code: add_embedding_estimate(company, embedding_dimension)
        for code, company in result["companies"].items()
    }
    result["external_sources"] = [
        {"provider": provider.__class__.__name__, "inventory": provider.inventory()}
        for provider in providers
    ]
    return add_embedding_estimate(result, embedding_dimension)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="기업별 RAG 코퍼스 재구축")
    parser.add_argument("--corp-code", action="append", help="재구축할 8자리 기업 코드 (여러 번 지정 가능)")
    parser.add_argument("--dry-run", action="store_true", help="삭제·삽입 없이 입력과 변환 결과만 집계")
    parser.add_argument("--dart-archive", type=Path, help="사업보고서 XML과 manifest가 든 ZIP")
    parser.add_argument("--embedding-dimension", type=int, default=1024,
                        help="float32 벡터 저장량 추정에 쓸 차원 (기본: 1024)")
    args = parser.parse_args(argv)
    if args.embedding_dimension <= 0:
        parser.error("--embedding-dimension은 양수여야 합니다")
    return args


def main() -> int:
    args = parse_args()
    try:
        with ExitStack() as stack:
            providers: list[ExternalEvidenceProvider] = []
            if args.dart_archive:
                archive = stack.enter_context(DartArchive(args.dart_archive))
                providers.append(BusinessReportSource(archive))
            summary = run(
                connect, args.corp_code, dry_run=args.dry_run, external_providers=providers,
                embedding_dimension=args.embedding_dimension,
            )
    except Exception as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False))
        return 1
    partial = bool(summary["failures"])
    print(json.dumps({"status": "partial" if partial else "success", **summary}, ensure_ascii=False, sort_keys=True))
    return 1 if partial else 0


if __name__ == "__main__":
    raise SystemExit(main())

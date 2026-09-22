"""기존 근거·임베딩 해시를 바꾸지 않고 사업보고서 표의 소속 법인을 적재한다."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.raw_sources.chunking_profiles import get_chunking_profile  # noqa: E402
from pipeline.raw_sources.dart_archive import DartArchive  # noqa: E402
from pipeline.raw_sources.entity_scope import scope_rows  # noqa: E402


_WORKER_ARCHIVE: DartArchive | None = None
_WORKER_PROFILE = None


def _init_scope_worker(archive_path: str, profile_name: str) -> None:
    global _WORKER_ARCHIVE, _WORKER_PROFILE
    _WORKER_ARCHIVE = DartArchive(archive_path)
    _WORKER_PROFILE = get_chunking_profile(profile_name)


def _collect_one_company(corp_code: str) -> tuple[str, list[tuple[str, str, str, int]]]:
    if _WORKER_ARCHIVE is None or _WORKER_PROFILE is None:
        raise RuntimeError("소속 법인 백필 워커가 초기화되지 않았습니다")
    return corp_code, scope_rows(_WORKER_ARCHIVE, corp_code, _WORKER_PROFILE)


def _backfill_one_company(corp_code: str) -> tuple[str, dict[str, int]]:
    """워커 안에서 파싱 결과를 즉시 적재해 큰 행 목록의 IPC 전달을 피한다."""
    _, rows = _collect_one_company(corp_code)
    from pipeline.db import connect

    with connect() as connection:
        return corp_code, write_scope_rows(connection, rows)


def collect_company_scope_rows(
    archive_path: Path, corp_codes: list[str], profile_name: str, *, workers: int,
) -> list[tuple[str, list[tuple[str, str, str, int]]]]:
    """기업별 XML 파싱만 병렬화하고 DB 쓰기는 호출자에서 직렬화한다."""
    if workers < 1:
        raise ValueError("workers는 1 이상이어야 합니다")
    if workers == 1:
        with DartArchive(archive_path) as archive:
            profile = get_chunking_profile(profile_name)
            return [(corp_code, scope_rows(archive, corp_code, profile)) for corp_code in corp_codes]
    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=_init_scope_worker,
        initargs=(str(archive_path), profile_name),
    ) as executor:
        return list(executor.map(_collect_one_company, corp_codes, chunksize=1))


def backfill_company_scope_rows(
    archive_path: Path, corp_codes: list[str], profile_name: str, *, workers: int,
) -> list[tuple[str, dict[str, int]]]:
    """기업별 XML 파싱·UPSERT를 같은 워커에서 수행하고 집계값만 회수한다."""
    if workers < 1:
        raise ValueError("workers는 1 이상이어야 합니다")
    if workers == 1:
        with DartArchive(archive_path) as archive:
            profile = get_chunking_profile(profile_name)
            result = []
            from pipeline.db import connect

            for corp_code in corp_codes:
                rows = scope_rows(archive, corp_code, profile)
                with connect() as connection:
                    result.append((corp_code, write_scope_rows(connection, rows)))
            return result
    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=_init_scope_worker,
        initargs=(str(archive_path), profile_name),
    ) as executor:
        return list(executor.map(_backfill_one_company, corp_codes, chunksize=1))


_UPSERT = """
INSERT INTO rag_evidence_entity_scope
    (evidence_id, scope_name, rcept_no, table_index, rule_version)
VALUES (%s, %s, %s, %s, 'bracket-heading-v1')
ON CONFLICT (evidence_id) DO UPDATE SET
    scope_name = EXCLUDED.scope_name,
    rcept_no = EXCLUDED.rcept_no,
    table_index = EXCLUDED.table_index,
    rule_version = EXCLUDED.rule_version,
    updated_at = now()
WHERE (rag_evidence_entity_scope.scope_name,
       rag_evidence_entity_scope.rcept_no,
       rag_evidence_entity_scope.table_index,
       rag_evidence_entity_scope.rule_version)
      IS DISTINCT FROM
      (EXCLUDED.scope_name, EXCLUDED.rcept_no,
       EXCLUDED.table_index, EXCLUDED.rule_version)
"""


def write_scope_rows(connection, rows: list[tuple[str, str, str, int]]) -> dict[str, int]:
    """존재하는 근거 ID만 쓰고 미연결 건수를 보고한다. 트랜잭션은 호출자가 관리한다."""
    unique_rows = list({row[0]: row for row in rows}.values())
    if not unique_rows:
        return {"candidate_count": 0, "matched_count": 0, "missing_count": 0}
    cursor = connection.cursor()
    cursor.execute(
        "SELECT evidence_id FROM rag_evidence WHERE evidence_id = ANY(%s)",
        ([row[0] for row in unique_rows],),
    )
    known = {record[0] for record in cursor.fetchall()}
    matched = [row for row in unique_rows if row[0] in known]
    if matched:
        cursor.executemany(_UPSERT, matched)
    return {
        "candidate_count": len(unique_rows),
        "matched_count": len(matched),
        "missing_count": len(unique_rows) - len(matched),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="사업보고서 표의 소속 법인 보조 테이블 백필")
    parser.add_argument("--dart-archive", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--profile", default="adaptive-v1")
    parser.add_argument(
        "--workers", type=int, default=min(8, os.cpu_count() or 1),
        help="기업별 XML 파싱·UPSERT 프로세스 수. 기본값은 최대 8개입니다.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--quiet", action="store_true", help="기업별 진행 로그를 출력하지 않습니다.")
    args = parser.parse_args(argv)

    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    codes = sorted({row["corp_code"] for row in selection["companies"]})
    profile = get_chunking_profile(args.profile)
    if args.workers < 1:
        parser.error("--workers는 1 이상이어야 합니다")
    results = {}
    if args.dry_run:
        company_results = [
            (corp_code, {"candidate_count": len(rows), "matched_count": None, "missing_count": None})
            for corp_code, rows in collect_company_scope_rows(
                args.dart_archive, codes, profile.name, workers=args.workers,
            )
        ]
    else:
        company_results = backfill_company_scope_rows(
            args.dart_archive, codes, profile.name, workers=args.workers,
        )
    for corp_code, result in company_results:
        results[corp_code] = result
        if not args.quiet:
            print(json.dumps({"corp_code": corp_code, **result}, ensure_ascii=False), flush=True)
    payload = {"profile": profile.name, "company_count": len(codes), "companies": results}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

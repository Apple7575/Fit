"""사업보고서 서식 표 행을 company_table_row 에 적재한다 (V33, docs/decisions/0003).

    python data/scripts/load_form_table_rows.py --dart-archive outputs/dart-local-extracted --selection <기업목록.json> --workers 8
    python data/scripts/load_form_table_rows.py --dart-archive ... --corp-code 01021666 --dry-run --output out.json

기업 단위로 기존 행을 지우고 다시 넣는다(한 트랜잭션). 접속은 DATABASE_URL(.env)이고, 워커가 파싱 뒤 바로
적재해 큰 행 목록을 프로세스 간에 넘기지 않는다(소속 법인 백필과 같은 방식). 청크·임베딩은 건드리지 않는다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.rag_corpus.form_table_rows import company_records, forms_of, summarize, write_company_rows  # noqa: E402
from pipeline.raw_sources.chunking_profiles import get_chunking_profile  # noqa: E402
from pipeline.raw_sources.dart_archive import DartArchive  # noqa: E402

_ARCHIVE: DartArchive | None = None
_PROFILE = None


def _init_worker(archive_path: str, profile_name: str) -> None:
    global _ARCHIVE, _PROFILE
    _ARCHIVE = DartArchive(archive_path)
    _PROFILE = get_chunking_profile(profile_name)


def _dry_run_one(corp_code: str) -> tuple[str, dict]:
    assert _ARCHIVE is not None and _PROFILE is not None
    started = time.perf_counter()
    failures: list[dict] = []
    records = company_records(_ARCHIVE, corp_code, _PROFILE, failures)
    return corp_code, {**summarize(records), "forms": forms_of(records), "failures": failures, "seconds": round(time.perf_counter() - started, 1)}


def _load_one(corp_code: str) -> tuple[str, dict]:
    assert _ARCHIVE is not None and _PROFILE is not None
    from pipeline.db import connect

    started = time.perf_counter()
    failures: list[dict] = []
    records = company_records(_ARCHIVE, corp_code, _PROFILE, failures)
    with connect() as connection:
        result = write_company_rows(connection, corp_code, records)
    return corp_code, {**result, "forms": forms_of(records), "failures": failures, "seconds": round(time.perf_counter() - started, 1)}


def run(archive_path: Path, corp_codes: list[str], profile_name: str, *, workers: int, dry_run: bool) -> dict[str, dict]:
    work = _dry_run_one if dry_run else _load_one
    if workers < 1:
        raise ValueError("workers는 1 이상이어야 합니다")
    if workers == 1:
        _init_worker(str(archive_path), profile_name)
        return dict(work(code) for code in corp_codes)
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker, initargs=(str(archive_path), profile_name)) as executor:
        return dict(executor.map(work, corp_codes, chunksize=1))


def _selection_codes(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [str(item["corp_code"] if isinstance(item, dict) else item) for item in data]
    codes: list[str] = []
    for value in data.values():
        if isinstance(value, list):
            codes.extend(str(item["corp_code"] if isinstance(item, dict) else item) for item in value)
    return codes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dart-archive", type=Path, required=True)
    parser.add_argument("--selection", type=Path, help="기업 목록 JSON (experiment-100-v1.json 형식 또는 코드 배열)")
    parser.add_argument("--corp-code", action="append", default=[])
    parser.add_argument("--profile", default="adaptive-v1")
    parser.add_argument("--workers", type=int, default=max(1, min(8, (os.cpu_count() or 2) - 1)))
    parser.add_argument("--dry-run", action="store_true", help="DB 에 쓰지 않고 집계만")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    codes = list(dict.fromkeys([*(_selection_codes(args.selection) if args.selection else []), *args.corp_code]))
    if not codes:
        parser.error("--selection 또는 --corp-code 가 필요합니다")
    started = time.perf_counter()
    results = run(args.dart_archive, codes, args.profile, workers=args.workers, dry_run=args.dry_run)
    if not args.quiet:
        for code, r in results.items():
            print(f"[{code}] tables={r['table_count']} rows={r['row_count']} numbers={r['number_count']} misaligned={r['misaligned_count']} unmatched={r['evidence_unmatched']} {r['seconds']}s", file=sys.stderr)
    total = {
        "company_count": len(results),
        "table_count": sum(r["table_count"] for r in results.values()),
        "row_count": sum(r["row_count"] for r in results.values()),
        "number_count": sum(r["number_count"] for r in results.values()),
        "misaligned_count": sum(r["misaligned_count"] for r in results.values()),
        "evidence_unmatched": sum(r["evidence_unmatched"] for r in results.values()),
        "document_failures": sum(len(r["failures"]) for r in results.values()),
        "elapsed_s": round(time.perf_counter() - started, 1),
        "dry_run": args.dry_run,
        "profile": args.profile,
    }
    payload = {"summary": total, "companies": results}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(total, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

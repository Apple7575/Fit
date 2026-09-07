"""수집기 출력 폴더를 raw 계층으로 들여온다 (복사, 원본 훼손 없음).

    python scripts/import_news_raw.py --from ../data/news_poc/local_raw/sample-0906
    python scripts/import_news_raw.py --from <폴더> --run-id 20260907T031500Z-a1b2c3d4

수집기(`collect.py`)의 `--out` 폴더는 실행자가 이름을 정하므로 저장 기준의
경로 규칙과 맞지 않는다. 이 스크립트가 `data/raw/google_news_rss/articles/<run_id>/`
로 **복사**하고, 옮기기 전후의 파일 수·바이트·SHA-256 을 대조한다(기준 문서 10장).

원본을 지우지 않는다. `--move` 같은 옵션은 두지 않았다 — 원본이 유일본인 동안
이동은 되돌릴 수 없다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.news import manifest as manifest_mod  # noqa: E402
from pipeline.news import rawstore, stage  # noqa: E402
from pipeline.news.schema import PROVIDER  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from", dest="source", type=Path, required=True,
                        help="수집기 --out 폴더 (RSS XML + requests.json)")
    parser.add_argument("--run-id", help="생략하면 <UTC시각>-<난수8> 로 만든다")
    parser.add_argument("--target-start", help="KST 대상 시작일 (YYYY-MM-DD). 생략하면 요청 계획에서 도출")
    parser.add_argument("--target-end", help="KST 대상 종료일, exclusive")
    parser.add_argument("--dry-run", action="store_true", help="복사하지 않고 대조 결과만 본다")
    args = parser.parse_args()

    source = args.source.resolve()
    if not source.is_dir():
        parser.error(f"폴더가 없다: {source}")
    xml_files = sorted(source.glob("*.xml"))
    if not xml_files:
        parser.error(f"RSS XML 이 없다: {source} — 표본 데이터를 만들지 않는다")

    run_id = args.run_id or rawstore.mint_run_id()
    if not rawstore.RUN_ID_RE.match(run_id):
        print(f"경고: run_id 가 규칙(<YYYYMMDDThhmmssZ>-<8자리 hex>)과 다르다: {run_id}")
    destination = rawstore.run_dir(run_id)
    if destination.exists() and any(destination.iterdir()):
        parser.error(f"이미 있는 수집 실행이다. 원본을 덮어쓰지 않는다: {destination}")

    before = {path.name: (path.stat().st_size, _sha256(path)) for path in xml_files}
    requests_path = source / "requests.json"
    if requests_path.exists():
        before["requests.json"] = (requests_path.stat().st_size, _sha256(requests_path))
    else:
        print("경고: requests.json 이 없다. 요청 이력·수집 시각을 manifest 에 담을 수 없다")

    print(f"원본  {source}")
    print(f"대상  {destination}")
    print(f"파일  XML {len(xml_files)}건, 총 {sum(v[0] for v in before.values()):,} bytes")
    if args.dry_run:
        for name, (size, digest) in before.items():
            print(f"  {name:24s} {size:>10,} {digest[:16]}…")
        return 0

    destination.mkdir(parents=True, exist_ok=True)
    for name in before:
        shutil.copy2(source / name, destination / name)

    problems = []
    after = {}
    for name, (size, digest) in before.items():
        target = destination / name
        after[name] = (target.stat().st_size, _sha256(target))
        if after[name] != (size, digest):
            problems.append(f"{name}: 복사 전후 불일치")
    copied = sorted(p.name for p in destination.iterdir() if p.name in before)
    if len(copied) != len(before):
        problems.append(f"파일 수 불일치: {len(before)} → {len(copied)}")

    run = rawstore.load_run(run_id)
    derived_start, derived_end = stage.derive_target_window(run)
    target_start = args.target_start or derived_start
    target_end = args.target_end or derived_end
    for value in (target_start, target_end):
        if value:
            date.fromisoformat(value)

    (destination / "run.json").write_text(json.dumps({
        "provider": PROVIDER,
        "collection_run_id": run_id,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "source_directory": str(source),
        "target_start": target_start,
        "target_end_exclusive": target_end,
        "target_window_source": "cli" if args.target_start else "derived_from_requests_json",
        "queries": run.queries(),
        "files": {name: {"bytes": v[0], "sha256": v[1]} for name, v in sorted(after.items())},
        "note": "원본은 읽기만 한다. 컬럼·값을 고치지 않으며 중복 기사도 지우지 않는다.",
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    document = manifest_mod.build(run, target_start, target_end)
    path = manifest_mod.write(document)
    print(f"manifest  {path.relative_to(rawstore.ROOT.parent)}")
    print(f"레코드    {document['record_count']}건 (고유 {document['unique_article_keys']}, "
          f"중복 후보 {document['duplicate_candidate_count']})")
    print(f"요청      성공 {document['success_count']} / 실패 {document['fail_count']}")
    print(f"대상 구간 {target_start} ~ {target_end} (exclusive)")

    if problems:
        print("\n실패:")
        for line in problems:
            print("  " + line)
        return 1
    print("\n복사 전후 파일 수·바이트·SHA-256 일치")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""staged → curated. `company_news` 시드 CSV 를 만든다.

    python scripts/build_news_seed.py
    python scripts/build_news_seed.py --source-column provider

헤더는 Flyway 의 `company_news` 컬럼과 일치하고 identity 컬럼 `id` 는 넣지 않는다.
corp_code 가 없는 행, 길이 위반 행, 중복 (corp_code, original_url) 행은 넣지 않고
사유와 함께 `staged/google_news_rss/seed_dropped.csv` 에 남긴다.

staged 가 비어 있으면 **빈 시드 파일을 만들지 않는다.** 헤더만 있는 CSV 를 커밋하면
시드가 있는 것처럼 보인다 — 그 상태는 `seed_csv_inventory.csv` 에서 missing 이다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# 콘솔이 cp949 면 docstring 의 '—' 에서 죽는다 (--help 가 그랬다). 형제 스크립트들과
# 같은 처리다.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

from pipeline import seed_guard  # noqa: E402
from pipeline.news import curate, flyway  # noqa: E402
from pipeline.news.schema import SEED_SOURCE_CHOICES, SEED_SOURCE_DEFAULT, SEED_TABLE  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source-column", choices=SEED_SOURCE_CHOICES, default=SEED_SOURCE_DEFAULT,
                        help="company_news.source 에 무엇을 담을지. 백엔드 합의 필요 항목")
    parser.add_argument("--collected-at-fallback", default="",
                        help="collected_at 이 빈 행에 쓸 값. 기본은 비움(그 행은 제외된다)")
    parser.add_argument("--allow-empty", action="store_true",
                        help="staged 가 비어도 헤더만 있는 시드를 쓴다")
    parser.add_argument("--per-company", type=int, default=0, metavar="N",
                        help="기업마다 최신 N 건만 남긴다. 0 이면 전부 (기본)")
    seed_guard.add_arguments(parser)
    args = parser.parse_args()
    if args.per_company < 0:
        parser.error("--per-company 는 0 이상이어야 한다")

    schema = flyway.load()
    staged_dir = curate.SEED_DIR.parents[1] / "staged" / "google_news_rss"
    rows = curate.load_staged(staged_dir)
    print(f"Flyway   {len(schema.applied_files)}개 마이그레이션, {SEED_TABLE} 컬럼 "
          f"{len(schema.table(SEED_TABLE).columns)}개")
    print(f"staged   {len(rows)}행  ({staged_dir.relative_to(staged_dir.parents[2])})")
    if not rows and not args.allow_empty:
        print("\nstaged 행이 없어 시드를 만들지 않는다.")
        print("  scripts/stage_news.py 를 먼저 돌린다. 원본이 없으면 표본을 만들지 않는다.")
        print(f"  현재 상태는 docs/seed_csv_inventory.csv 의 {SEED_TABLE} 행에서 확인한다.")
        return 0

    result = curate.build(rows, schema, args.source_column, args.collected_at_fallback,
                          per_company=args.per_company)
    # 직전 시드보다 급감하면 여기서 멈춘다. 뉴스는 증분 수집이라 staged 가 일부만
    # 있는 채로 돌면 시드가 조용히 작아진다 — CSV 는 커밋하지 않지만 적재는 이
    # 파일로 간다 (docs/news-poc).
    seed_guard.check(SEED_TABLE, result.rows, manifest_dir=curate.SEED_MANIFEST_DIR,
                     max_drop=args.max_drop, allow_shrink=args.allow_shrink)
    paths = curate.write(result)
    summary = result.summary
    if args.per_company:
        print(f"선별     기업마다 최신 {args.per_company}건")
    print(f"\n시드     {summary['seed_rows']}행 → {paths['seed']}")
    print(f"헤더     {','.join(summary['header'])}")
    print(f"source   → {summary['source_column_maps_to']}  (백엔드 합의 필요)")
    print(f"제외     {summary['dropped_rows']}행 {summary['drop_reasons'] or ''}")
    print(f"기업     {summary['distinct_corp_codes']}개")
    print(f"결측     published_at null {summary['published_at_null_rows']}, "
          f"original_url null {summary['original_url_null_rows']}, "
          f"AI 컬럼 전부 null ({', '.join(summary['ai_columns_null'])})")
    print(f"manifest {paths['manifest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

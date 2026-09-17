"""수집 실행 CLI (WP-5).

    python scripts/collect.py                          # 타깃 전체 x 기본 연도
    python scripts/collect.py --years 2024 2025
    python scripts/collect.py --corp 00126380          # 특정 기업만
    python scripts/collect.py --retry _log/failed_ab12cd34ef56.csv
    python scripts/collect.py --dry-run                # 무엇을 받을지만 보여준다
    python scripts/collect.py --targets config/targets_baseline.csv   # 회귀 기준선 10개사

캐시에 이미 있으면 호출하지 않는다(outcome=cached). 로그는 `_log/ingest_log.csv`
에 이어붙고, 실패가 있으면 `_log/failed_<run_id>.csv` 가 생긴다. 그 파일을
그대로 --retry 에 넣으면 실패한 기업-연도만 다시 돈다.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.collect import DEFAULT_YEARS, Collector, load_failed  # noqa: E402
from pipeline.dart_client import DartClient  # noqa: E402
from pipeline.targets import load_targets  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="DART 원본 수집")
    ap.add_argument("--years", type=int, nargs="+", default=list(DEFAULT_YEARS))
    ap.add_argument("--corp", nargs="+", help="corp_code 또는 표시명으로 대상 한정")
    ap.add_argument("--profile", action="store_true",
                    help="기업개황(company.json)만 수집한다. 기업당 1콜, 연도 무관")
    ap.add_argument("--targets", type=Path,
                    help="대상 목록 CSV. 기본값은 config/targets.csv. "
                         "회귀 기준선 재수집은 config/targets_baseline.csv 를 쓴다")
    ap.add_argument("--retry", type=Path, help="failed_*.csv 를 입력으로 실패분만 재실행")
    ap.add_argument("--no-cache", action="store_true", help="캐시를 무시하고 새로 받는다")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")

    targets = load_targets(args.targets)
    if args.corp:
        want = set(args.corp)
        targets = [t for t in targets if t.corp_code in want or t.display_name in want]
        if not targets:
            print(f"대상을 찾지 못했다: {args.corp}")
            return 1

    only = load_failed(args.retry) if args.retry else None
    years = tuple(args.years)

    if args.dry_run:
        return _dry_run(targets, years, only)

    collector = Collector(DartClient(use_cache=not args.no_cache))
    run = (collector.run_profiles(targets) if args.profile
           else collector.run(targets, years=years, only=only))

    print(f"run_id      {run.run_id}")
    print(f"기간        {run.started_at} ~ {run.finished_at}")
    print(f"대상        기업-연도 {run.pairs}건 (기업 {len(targets)} x 연도 {len(years)} 중)")
    print("결과       ", ", ".join(f"{k} {v}" for k, v in sorted(run.outcomes.items())))
    st = collector.client.stats
    print(f"호출        실제 {st.calls} / 캐시 {st.cache_hits} / 재시도 {st.retries} "
          f"/ 빈결과 {st.empty} / {st.bytes_in / 1e6:.1f}MB")
    print(f"로그        {run.log_path}")
    if run.fail_path:
        print(f"실패 {run.failed}건 → {run.fail_path}")
        print(f"재실행      python scripts/collect.py --retry {run.fail_path}")
        return 1
    print("실패        없음")
    return 0


def _dry_run(targets, years, only) -> int:
    total = 0
    for t in targets:
        for y in years:
            if only is not None and (t.corp_code, y) not in only:
                continue
            if not t.is_listed(y):
                print(f"  skip  {t.display_name:<10} {y}  상장 이전({t.listed_from})")
                continue
            print(f"  call  {t.display_name:<10} {y}  주요계정/전체CFS/전체OFS/직원/사업보고서")
            total += 5
    print(f"\n최대 {total}콜 (캐시에 있으면 호출하지 않는다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

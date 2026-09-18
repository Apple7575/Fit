"""뉴스 데이터 검증 15종 (data/docs/DATA_STORAGE_STANDARD.md 11장).

    python scripts/verify_news.py
    python scripts/verify_news.py --json _out/news_verify.json

DB 에 붙지 않는다. 스키마는 Flyway SQL 에서 읽고, FK 대조는 기업 마스터의 원천인
`config/company_universe.csv` 로 한다.

원본·정제 결과가 없는 항목은 `SKIP` 이며 `PASS` 로 세지 않는다. 종료 코드는 실패가
하나라도 있으면 1 이다 — SKIP 은 0 이지만 요약에 건수가 그대로 나온다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.news import verify  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", type=Path, help="검증 결과를 JSON 으로도 쓴다")
    parser.add_argument("--verbose", action="store_true", help="항목별 상세를 모두 출력한다")
    args = parser.parse_args()

    checks = verify.run_all()
    print("뉴스 데이터 검증")
    print("=" * 64)
    for check in checks:
        print(check.line)
        detail = check.detail
        if check.status == "skip":
            print(f"        {detail.get('reason', '')}")
            continue
        problems = detail.get("problems") or []
        for line in problems:
            print(f"        ! {line}")
        if args.verbose or (check.status == "fail" and not problems):
            print("        " + json.dumps(detail, ensure_ascii=False, sort_keys=True)[:600])

    counts = {status: sum(1 for c in checks if c.status == status)
              for status in ("pass", "fail", "skip")}
    print("=" * 64)
    print(f"통과 {counts['pass']} · 실패 {counts['fail']} · 건너뜀 {counts['skip']}  (총 {len(checks)})")
    if counts["skip"]:
        print("건너뛴 항목은 원본·정제 결과가 없어 검증하지 못한 것이다. 통과가 아니다.")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(
            {"summary": counts,
             "checks": [{"number": c.number, "name": c.name, "status": c.status,
                         "detail": c.detail} for c in checks]},
            ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"→ {args.json}")
    return 1 if counts["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

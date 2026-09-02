"""정규화 실행 CLI (WP-6).

`.cache/` 의 원본을 읽어 지표 값을 만든다. **API 를 호출하지 않는다** — 원본이
없으면 그 지표를 `not_found` 로 기록하고 넘어간다(`scripts/collect.py` 를 먼저 돌릴 것).

    python scripts/normalize.py                     # 타깃 전체 x 기본 연도
    python scripts/normalize.py --corp 삼성전자 --years 2025
    python scripts/normalize.py --show              # 표로 출력만, 파일 안 씀

산출물 (`_out/`, DESIGN 5장의 적재 입력)

    company_year.csv       기업-연도 1행 (wide)
    metric_evidence.csv    지표별 근거·판정 1행
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.collect import DEFAULT_YEARS  # noqa: E402
from pipeline.normalize.runner import CompanyYear, normalize_one  # noqa: E402
from pipeline.paths import ROOT  # noqa: E402
from pipeline.rawstore import RawStore  # noqa: E402
from pipeline.targets import load_targets  # noqa: E402

OUT = ROOT / "_out"
EVIDENCE_FIELDS = ["corp_code", "bsns_year", "metric_code", "verdict", "source",
                   "gap_pct", "evidence"]


def main() -> int:
    ap = argparse.ArgumentParser(description="원본 → 지표 정규화")
    ap.add_argument("--years", type=int, nargs="+", default=list(DEFAULT_YEARS))
    ap.add_argument("--corp", nargs="+", help="corp_code 또는 표시명으로 대상 한정")
    ap.add_argument("--show", action="store_true", help="파일을 쓰지 않고 표로만 출력")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.ERROR,
                        format="%(levelname)s %(name)s: %(message)s")

    targets = load_targets()
    if args.corp:
        want = set(args.corp)
        targets = [t for t in targets if t.corp_code in want or t.display_name in want]
        if not targets:
            print(f"대상을 찾지 못했다: {args.corp}")
            return 1

    store = RawStore()
    rows: list[CompanyYear] = []
    evidence: list[dict] = []
    verdicts: Counter = Counter()
    skipped = 0
    warned: list[tuple[str, int, str]] = []

    print(f"{'기업':<10}{'연도':<6}{'매출(조)':>10}{'영업이익(조)':>13}"
          f"{'직원':>8}{'근속':>7}{'급여(만)':>10}{'R&D(조)':>9}{'비율%':>7}  판정")
    print("-" * 104)

    for t in targets:
        for year in args.years:
            res = normalize_one(store, t, year)
            if res.skipped:
                skipped += 1
                print(f"{t.display_name:<10}{year:<6}{'— 상장 이전':>10}")
                continue

            r = res.row
            rows.append(r)
            evidence.extend(e.as_row() for e in res.evidence)
            for e in res.evidence:
                verdicts[e.verdict] += 1
            for w in res.warnings:
                warned.append((t.display_name, year, w))

            print(f"{t.display_name:<10}{year:<6}"
                  f"{_t(r.revenue):>10}{_t(r.operating_profit):>13}"
                  f"{_i(r.employee_count):>8}{_f(r.avg_tenure_years):>7}"
                  f"{_man(r.avg_salary_krw):>10}{_t(r.rnd_cost_krw):>9}"
                  f"{_f(r.rnd_ratio_pct):>7}  "
                  + " ".join(f"{e.metric_code.split('_')[0]}:{e.verdict[:4]}"
                             for e in res.evidence if e.verdict != "verified") or "  전부 verified")

    print(f"\n기업-연도 {len(rows)}건 정규화 / {skipped}건 상장 이전 제외")
    print("지표 판정:", dict(verdicts))
    if warned:
        print(f"\n경고 {len(warned)}건")
        for name, year, w in warned[:20]:
            print(f"  {name} {year}  {w}")

    if args.show:
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    cy_path = OUT / "company_year.csv"
    with cy_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()) if rows else [])
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))

    ev_path = OUT / "metric_evidence.csv"
    with ev_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=EVIDENCE_FIELDS)
        w.writeheader()
        w.writerows(evidence)

    print(f"\n{cy_path}  {len(rows)}행")
    print(f"{ev_path}  {len(evidence)}행")
    return 0


def _t(v):      # 조 단위
    return f"{v / 1e12:,.2f}" if v else "-"


def _i(v):
    return f"{v:,}" if v else "-"


def _f(v):
    return f"{v:.2f}" if v else "-"


def _man(v):    # 만원
    return f"{v / 1e4:,.0f}" if v else "-"


if __name__ == "__main__":
    raise SystemExit(main())

"""staged → curated. 회사 × 연도 × 계정 넓은 표.

**당기(thstrm)만 쓴다.** 전기·전전기 값은 검산용이지 적재 대상이 아니다 —
연도 교차 검산에서 1,026개사가 어긋났고(소급 재작성), 어느 쪽을 정본으로 볼지는
아직 정해지지 않았다. 각 연도의 **그 해 보고서가 말한 값**을 담는 것이 기본값이다.

연결·별도는 접지 않는다. CFS 가 있으면 CFS, 없으면 OFS 를 쓰는 폴백은 **해석**이라
소비처가 정한다. 대신 어느 쪽이 있는지 `fs_div` 로 남긴다.

    python scripts/build_financials_seed.py
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.paths import curated_seed_dir, staged_dir

ACCOUNTS = ["매출액", "영업이익", "법인세차감전 순이익", "당기순이익(손실)", "총포괄손익",
            "자산총계", "부채총계", "자본총계", "자본금", "이익잉여금",
            "유동자산", "비유동자산", "유동부채", "비유동부채"]

COL = {a: a.replace("(손실)", "").replace(" ", "_") for a in ACCOUNTS}

# 같은 뜻인데 원천이 이름을 둘로 쓴다. '영업이익' 으로만 거르면 71개사(332행)가
# 통째로 빠진다. 두 이름이 한 (회사·연도·fs_div) 에 같이 오는 경우는 0건이라
# 같은 칸에 넣어도 덮어쓰지 않는다 — 실측으로 확인했다.
COL["영업이익(손실)"] = "영업이익"


def main() -> int:
    src = staged_dir() / "financials.csv"
    rows = list(csv.DictReader(src.open(encoding="utf-8")))
    print(f"staged {len(rows):,}행")

    cells: dict[tuple, dict] = defaultdict(dict)
    meta: dict[tuple, dict] = {}
    for r in rows:
        key = (r["corp_code"], r["bsns_year"], r["fs_div"])
        if r["account_nm"] in COL:
            cells[key][COL[r["account_nm"]]] = r["thstrm_amount"]
        meta.setdefault(key, {"stock_code": r["stock_code"], "currency": r["currency"],
                              "fs_nm": r["fs_nm"], "rcept_no": r["rcept_no"],
                              "thstrm_dt": r["thstrm_dt"]})

    fields = (["corp_code", "stock_code", "bsns_year", "fs_div", "fs_nm", "currency"]
              + list(COL.values()) + ["rcept_no", "기준일"])
    out = curated_seed_dir() / "company_financials.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for key in sorted(cells):
            corp, year, fs = key
            m = meta[key]
            row = {"corp_code": corp, "stock_code": m["stock_code"], "bsns_year": year,
                   "fs_div": fs, "fs_nm": m["fs_nm"], "currency": m["currency"],
                   "rcept_no": m["rcept_no"], "기준일": m["thstrm_dt"]}
            row.update(cells[key])
            w.writerow(row)

    corps = {k[0] for k in cells}
    both = defaultdict(set)
    for c, y, fs in cells:
        both[(c, y)].add(fs)
    print(f"curated {len(cells):,}행 (회사×연도×fs_div) · 회사 {len(corps):,}")
    print(f"  연결·별도 둘 다 {sum(1 for v in both.values() if len(v) == 2):,} "
          f"· 하나만 {sum(1 for v in both.values() if len(v) == 1):,}")
    filled = sum(1 for v in cells.values() if v.get("매출액"))
    print(f"  매출액이 있는 행 {filled:,} ({filled / len(cells):.1%})")
    print(f"→ {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

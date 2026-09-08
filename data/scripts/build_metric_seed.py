"""staged → curated/seed/company_metric.csv (확정 ERD 안의 테이블).

`company_metric` 은 **확정 ERD 명세서 안에 있고, 이미 존재하고, 조회 API 가 실제로
읽는 유일한 지표 테이블**이다 (`docs/design/db-schema.md` 3장). 착지 테이블은 명세
밖이라 승인을 기다려야 하지만, 이 시드는 **새 마이그레이션 없이 지금 적재된다.**

매핑 — v2 카탈로그의 FINANCIAL_STATEMENT 지표 5종이 전부 주요계정에 있다.

    revenue            매출액
    operating_profit   영업이익            ('영업이익(손실)' 도 같은 지표다)
    net_income         당기순이익(손실)
    total_liabilities  부채총계            (is_active = FALSE · debtRatio 입력)
    total_equity       자본총계            (is_active = FALSE · debtRatio 입력)

규칙 — 전부 기존 파이프라인과 같게 맞췄다

  ① 연결 우선, 없으면 별도. `patterns.yaml` 의 `fs_div_priority: [CFS, OFS]`
     어느 쪽을 썼는지 `fs_div` 에 **반드시 남긴다** (V1 주석)
  ② `metric_value` 가 NOT NULL 이므로 **결측은 행을 넣지 않는다.** null 로 채우지 않는다
  ③ 통화가 KRW 가 아니면 **넣지 않는다.** `metric.unit` 이 KRW 라서 USD 값을 그대로
     넣으면 단위가 틀린다. 환율을 우리가 정해 환산하는 것은 추정이므로 하지 않는다
     (S15P21A504-85 지시서 D-4). 제외 사유는 리포트에 남긴다

검증 — DB 에 이미 있는 10개사 값과 대조했다. `fnlttSinglAcntAll` 로 받아 다른 코드
경로로 만든 값인데 **233/233 이 정확히 일치**했다.

    python scripts/build_metric_seed.py
    python scripts/build_metric_seed.py --verify-db   # 기존 적재값과 대조
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.news.csvio import write_csv  # noqa: E402
from pipeline.paths import curated_seed_dir, staged_dir  # noqa: E402

# metric_code → 주요계정 이름
METRICS = {
    "revenue": "매출액",
    "operating_profit": "영업이익",
    "net_income": "당기순이익(손실)",
    "total_liabilities": "부채총계",
    "total_equity": "자본총계",
}

# 같은 뜻인데 원천이 이름을 둘로 쓴다 (실측: 71개사).
ALIAS = {"영업이익(손실)": "영업이익"}

FS_PRIORITY = ("CFS", "OFS")     # config/patterns.yaml 의 fs_div_priority

FIELDS = ["corp_code", "fiscal_year", "metric_code", "metric_value", "fs_div"]


def build_rows() -> tuple[list[dict], dict]:
    """staged/financials.csv → company_metric 행과 집계 수치.

    `scripts/build_curated_seed.py` 가 같은 규칙으로 다시 쓰지 않도록 뺐다.
    여기가 company_metric 매핑 규칙의 유일한 자리다.
    """
    src = staged_dir() / "financials.csv"
    rows = list(csv.DictReader(src.open(encoding="utf-8")))

    # (corp_code, year, fs_div) -> {계정명: (값, 통화)}
    box: dict[tuple, dict[str, tuple[float, str]]] = defaultdict(dict)
    for r in rows:
        if not r["thstrm_amount"]:
            continue
        acct = ALIAS.get(r["account_nm"], r["account_nm"])
        box[(r["corp_code"], int(r["bsns_year"]), r["fs_div"])][acct] = (
            float(r["thstrm_amount"]), r["currency"] or "")

    pairs = {(c, y) for c, y, _ in box}
    out: list[dict] = []
    used_fs = Counter()
    skipped_currency = Counter()
    missing = Counter()

    for corp, year in sorted(pairs):
        # ① 연결 우선, 없으면 별도. 한 쪽을 고르면 그 안에서만 값을 읽는다 —
        #    지표마다 연결·별도를 섞으면 debtRatio 가 서로 다른 재무제표의 비율이 된다.
        chosen = None
        for fs in FS_PRIORITY:
            if box.get((corp, year, fs)):
                chosen = fs
                break
        if chosen is None:
            continue
        acc = box[(corp, year, chosen)]
        used_fs[chosen] += 1

        for code, acct in METRICS.items():
            hit = acc.get(acct)
            if hit is None:
                missing[code] += 1
                continue
            value, currency = hit
            if currency and currency != "KRW":
                # ③ 단위가 다르다. 환산은 추정이므로 하지 않는다.
                skipped_currency[currency] += 1
                continue
            out.append({"corp_code": corp, "fiscal_year": year, "metric_code": code,
                        "metric_value": f"{value:.4f}", "fs_div": chosen})

    # 적재 순서를 고정한다 — 같은 입력이면 같은 바이트여야 한다 (저장 기준 9장)
    out.sort(key=lambda r: (r["corp_code"], r["fiscal_year"], r["metric_code"]))
    return out, {"staged_rows": len(rows), "pairs": len(pairs), "used_fs": used_fs,
                 "skipped_currency": skipped_currency, "missing": missing}


def write_seed(rows: list[dict]) -> Path:
    """BOM 없는 UTF-8 · LF 로 쓴다 (저장 기준 6장). 규칙은 csvio 한 곳에 있다."""
    dest = curated_seed_dir() / "company_metric.csv"
    write_csv(dest, FIELDS, rows)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-db", action="store_true",
                    help="DB 의 기존 company_metric 과 대조한다")
    args = ap.parse_args()

    out, stats = build_rows()
    pairs, used_fs = stats["pairs"], stats["used_fs"]
    skipped_currency, missing = stats["skipped_currency"], stats["missing"]
    print(f"staged {stats['staged_rows']:,}행")

    dest = write_seed(out)

    corps = len({r["corp_code"] for r in out})
    print(f"\n시드 {len(out):,}행 · 회사 {corps:,} · 기업-연도 {pairs:,}")
    print(f"  fs_div       연결 {used_fs['CFS']:,} · 별도 {used_fs['OFS']:,}")
    print(f"  지표별       " + " · ".join(
        f"{c} {sum(1 for r in out if r['metric_code'] == c):,}" for c in METRICS))
    print(f"  결측(행 없음) " + " · ".join(f"{c} {missing[c]:,}" for c in METRICS))
    if skipped_currency:
        print(f"  통화로 제외   {dict(skipped_currency)}  ← metric.unit 이 KRW 다")
    print(f"→ {dest}")

    if args.verify_db:
        from pipeline.db import connect
        seed = {(r["corp_code"], r["fiscal_year"], r["metric_code"]):
                float(r["metric_value"]) for r in out}
        with connect() as c, c.cursor() as cur:
            cur.execute("SELECT corp_code, fiscal_year, metric_code, metric_value "
                        "FROM company_metric WHERE metric_code = ANY(%s)",
                        (list(METRICS),))
            db = cur.fetchall()
        same = diff = absent = 0
        for corp, year, code, val in db:
            v = seed.get((corp, year, code))
            if v is None:
                absent += 1
            elif abs(float(val) - v) < 1:
                same += 1
            else:
                diff += 1
                print(f"    다름 {corp} {year} {code}: DB {float(val):,.0f} "
                      f"vs 시드 {v:,.0f}")
        print(f"\n[대조] DB {len(db):,}행 · 일치 {same:,} · 불일치 {diff} · "
              f"시드에 없음 {absent}")
        return 1 if diff else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())

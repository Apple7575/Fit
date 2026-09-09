"""사업보고서에서 온 시드 값을 검증한다 (S15P21A504-73).

DB 없이 CSV 만으로 돈다. 적재 전에 걸러야 할 것을 적재 전에 거르기 위해서다.

축 여덟 개
---------
    A  FK          네 표의 corp_code 가 company.csv 에 있나
    B  카탈로그     metric_code · attr_key · activity_type 이 허용된 값인가
    C  PK/UNIQUE   적재가 거부될 중복이 없나
    D  부문 합계    segment_revenue 합 == company_metric 의 revenue 인가
    E  R&D 상식     rd_expense / revenue 가 0~60% 인가
    F  시설투자     amount 가 양수이고 자릿수가 상식 범위인가
    G  company_text seq 가 0부터 연속인가, 값이 비지 않았나
    H  커버리지     기업·연도별로 무엇이 얼마나 찼나 (실패가 아니라 보고)

D 가 핵심이다. 부문 매출은 대조 상대가 전사 매출뿐이라, 이게 통과하지 않으면
열을 잘못 집었다는 뜻이다. 파싱 단계에서 이미 한 번 걸렀지만 시드를 손으로 고칠
수 있으므로 적재본에서 다시 본다.

    python scripts/verify_business_report.py
    python scripts/verify_business_report.py --report   # 커버리지까지
"""
from __future__ import annotations

import argparse
import collections
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.paths import curated_seed_dir  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

ATTR_KEYS = {"main_business", "main_product", "business_keyword",
             "new_business", "strategy_change", "rd_field"}
ACTIVITY_TYPES = {"facility", "corporate_invest", "ma", "transfer"}

# 부문 합계 허용 오차. config/patterns.yaml 의 segment_sum_tolerance 와 같은 값이다.
SEGMENT_SUM_TOLERANCE = 0.05
RD_RATIO_MAX = 60.0
# 시설투자 금액 상식 범위(원). 이 축의 목적은 **자릿수 사고**를 잡는 것이지
# 작은 투자를 걸러내는 것이 아니다.
#
# 처음에 하한을 1억으로 뒀더니 48건이 걸렸는데, 원문을 보니 둘로 갈렸다.
#   진짜 버그 23건 — 향후투자액을 읽었거나($ 금액) 통화가 달러였다. 파서를 고쳤다
#   정상   25건 — 아시아나항공 '에어서울 일반설비' 1,500만원처럼 한 표 안의 소액
#                 항목이다. 한화에어로스페이스는 1억~1,202억이 같은 표에 섞여 있다
#
# 그래서 하한을 100만원으로 내린다. 설비투자가 100만원 미만이면 단위를 잘못 읽은
# 것이고(효성티앤씨 '$15백만' → 15원 사건), 그 위는 회사가 그렇게 공시한 것이다.
FACILITY_MIN, FACILITY_MAX = 1e6, 2e14


class Report:
    def __init__(self) -> None:
        self.fails: list[str] = []
        self.axes: dict[str, tuple[int, int]] = {}

    def axis(self, name: str, title: str, bad: list[str], total: int) -> None:
        self.axes[name] = (len(bad), total)
        mark = "OK  " if not bad else "실패"
        print(f"[{name}] {mark} {title} — {total - len(bad)}/{total}")
        for b in bad[:8]:
            print(f"       {b}")
        if len(bad) > 8:
            print(f"       … 외 {len(bad) - 8}건")
        self.fails += [f"{name}: {b}" for b in bad]


def _read(name: str) -> list[dict]:
    path = curated_seed_dir() / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="커버리지 표까지 낸다")
    args = ap.parse_args()

    company = _read("company.csv")
    corp_codes = {r["corp_code"] for r in company}
    names = {r["corp_code"]: r["corp_name"] for r in company}
    metric = _read("company_metric.csv")
    segment = _read("segment_metric.csv")
    activity = _read("company_activity.csv")
    text = _read("company_text.csv")
    catalog = {r["metric_code"] for r in _read("metric.csv")}
    rep = Report()

    def label(c, y=None):
        return f"{names.get(c, c)}" + (f" {y}" if y else "")

    # ── A. FK
    bad, total = [], 0
    for tag, rows in (("company_metric", metric), ("segment_metric", segment),
                      ("company_activity", activity), ("company_text", text)):
        for r in rows:
            total += 1
            if r["corp_code"] not in corp_codes:
                bad.append(f"{tag}: company 에 없는 corp_code {r['corp_code']}")
    rep.axis("A", "FK — corp_code 가 company 에 있다", bad, total)

    # ── B. 카탈로그
    bad, total = [], 0
    for r in metric:
        total += 1
        if catalog and r["metric_code"] not in catalog:
            bad.append(f"company_metric: 카탈로그에 없는 metric_code {r['metric_code']}")
    for r in segment:
        total += 1
        if catalog and r["metric_code"] not in catalog:
            bad.append(f"segment_metric: 카탈로그에 없는 metric_code {r['metric_code']}")
    for r in activity:
        total += 1
        if r["activity_type"] not in ACTIVITY_TYPES:
            bad.append(f"company_activity: 허용 밖 activity_type {r['activity_type']}")
    for r in text:
        total += 1
        if r["attr_key"] not in ATTR_KEYS:
            bad.append(f"company_text: 허용 밖 attr_key {r['attr_key']}")
    rep.axis("B", "카탈로그 — metric_code·activity_type·attr_key", bad, total)

    # ── C. PK / UNIQUE
    bad = []
    for tag, rows, key in (
            ("company_metric", metric, ("corp_code", "fiscal_year", "metric_code")),
            ("segment_metric", segment,
             ("corp_code", "fiscal_year", "segment_name", "metric_code")),
            ("company_text", text, ("corp_code", "fiscal_year", "attr_key", "seq"))):
        seen = collections.Counter(tuple(r[k] for k in key) for r in rows)
        for k, n in seen.items():
            if n > 1:
                bad.append(f"{tag}: {k} 가 {n}번")
    rep.axis("C", "PK/UNIQUE — 중복 없음",
             bad, len(metric) + len(segment) + len(text))

    # ── D. 부문 합계 == 전사 매출
    revenue = {(r["corp_code"], r["fiscal_year"]): float(r["metric_value"])
               for r in metric if r["metric_code"] == "revenue" and r["metric_value"]}
    seg_sum: dict[tuple, float] = collections.defaultdict(float)
    for r in segment:
        if r["metric_code"] == "segment_revenue" and r["metric_value"]:
            seg_sum[(r["corp_code"], r["fiscal_year"])] += float(r["metric_value"])
    bad = []
    for key, total_krw in sorted(seg_sum.items()):
        rev = revenue.get(key)
        if rev is None:
            bad.append(f"{label(*key)}: 대조할 revenue 가 없다")
            continue
        gap = abs(total_krw - rev) / rev if rev else 1.0
        if gap > SEGMENT_SUM_TOLERANCE:
            bad.append(f"{label(*key)}: 부문합 {total_krw / 1e12:,.2f}조 vs "
                       f"매출 {rev / 1e12:,.2f}조 (오차 {gap:.1%})")
    rep.axis("D", "부문 합계 == 전사 매출", bad, len(seg_sum))

    # ── E. R&D 상식 범위
    bad, total = [], 0
    for r in metric:
        if r["metric_code"] != "rd_expense" or not r["metric_value"]:
            continue
        total += 1
        rev = revenue.get((r["corp_code"], r["fiscal_year"]))
        v = float(r["metric_value"])
        if v <= 0:
            bad.append(f"{label(r['corp_code'], r['fiscal_year'])}: rd_expense 가 {v}")
        elif rev and not (0 < v / rev * 100 <= RD_RATIO_MAX):
            bad.append(f"{label(r['corp_code'], r['fiscal_year'])}: "
                       f"R&D/매출 {v / rev * 100:.1f}% — 단위 오인 의심")
    rep.axis("E", f"rd_expense / revenue 가 0~{RD_RATIO_MAX:.0f}%", bad, total)

    # ── F. 시설투자 금액
    bad, total = [], 0
    for r in activity:
        if r["activity_type"] != "facility":
            continue
        total += 1
        if not r["amount"]:
            bad.append(f"{label(r['corp_code'], r['fiscal_year'])}: amount 가 비었다")
            continue
        v = float(r["amount"])
        if not (FACILITY_MIN <= v <= FACILITY_MAX):
            bad.append(f"{label(r['corp_code'], r['fiscal_year'])}: "
                       f"{r['field_name']} {v:,.0f}원 — 자릿수 확인")
        if r["counterparty"]:
            bad.append(f"{label(r['corp_code'], r['fiscal_year'])}: "
                       "facility 인데 counterparty 가 있다")
    rep.axis("F", "facility amount 가 상식 범위", bad, total)

    # ── G. company_text seq 와 값
    by_key: dict[tuple, list[int]] = collections.defaultdict(list)
    bad = []
    for r in text:
        if not r["value_text"].strip():
            bad.append(f"{label(r['corp_code'], r['fiscal_year'])} "
                       f"{r['attr_key']}: 값이 비었다")
        by_key[(r["corp_code"], r["fiscal_year"], r["attr_key"])].append(int(r["seq"]))
    for key, seqs in sorted(by_key.items()):
        if sorted(seqs) != list(range(len(seqs))):
            bad.append(f"{label(key[0], key[1])} {key[2]}: seq 가 0부터 연속이 아니다 "
                       f"{sorted(seqs)}")
    rep.axis("G", "company_text seq 가 0부터 연속 · 값이 있다", bad, len(by_key))

    # ── H. 커버리지 (실패가 아니라 보고)
    if args.report:
        print("\n커버리지")
        rd_pairs = {(r["corp_code"], r["fiscal_year"]) for r in metric
                    if r["metric_code"] == "rd_expense"}
        fac_pairs = {(r["corp_code"], r["fiscal_year"]) for r in activity
                     if r["activity_type"] == "facility"}
        txt = collections.Counter(r["attr_key"] for r in text)
        print(f"  segment_revenue   {len(seg_sum):>5,} 기업-연도 · "
              f"{len({c for c, _ in seg_sum}):,} 개사 · "
              f"{sum(1 for r in segment if r['metric_code'] == 'segment_revenue'):,} 행")
        print(f"  rd_expense        {len(rd_pairs):>5,} 기업-연도 · "
              f"{len({c for c, _ in rd_pairs}):,} 개사")
        print(f"  facility          {len(fac_pairs):>5,} 기업-연도 · "
              f"{len({c for c, _ in fac_pairs}):,} 개사 · "
              f"{sum(1 for r in activity if r['activity_type'] == 'facility'):,} 행")
        print(f"  company_text      {len(text):>5,} 행 — "
              + " · ".join(f"{k} {v:,}" for k, v in sorted(txt.items())))

    ok = sum(1 for f, _ in rep.axes.values() if f == 0)
    print(f"\n{ok}/{len(rep.axes)} 축 통과")
    if rep.fails:
        print(f"실패 {len(rep.fails)}건")
        return 1
    print("통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

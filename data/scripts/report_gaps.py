"""누락 사유 분류 리포트 (S15P21A504-86 Step 3).

    python scripts/report_gaps.py
    python scripts/report_gaps.py --csv     # _out/gaps.csv 도 쓴다

84 의 커버리지 리포트는 **확보율만** 보여준다. 이 리포트는 **없는 것의 사유**를
나눈다. 사유를 구분하지 않으면 "정상적으로 없는 것"과 "못 구한 것"이 섞여
커버리지가 왜곡된다.

사유 분류
--------
    값 있음        company_metric 에 행이 있다
    ① 미상장       targets.csv 의 listed_from 이전. **결측이 아니다**
    ② rejected     값을 신뢰할 수 없어 버렸다 (단위 미상 등)
    ③ not_found    찾지 못했다. 파서 한계
    ④ 수집 실패     API 오류. _log/ingest_log.csv 의 outcome=error
    ⑤ 근거 없음     값도 근거도 없다. 파이프라인이 아예 안 돈 구간

**①과 ④를 섞으면 안 된다.** 시프트업 2021~2023 은 사업보고서가 존재하지
않는 연도다. 이걸 "수집 실패"로 세면 커버리지가 실제보다 나쁘게 나오고,
반대로 진짜 실패를 "해당 없음"으로 세면 문제를 놓친다.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.collect import DEFAULT_YEARS  # noqa: E402
from pipeline.db import connect  # noqa: E402
from pipeline.paths import ROOT, log_dir  # noqa: E402
from pipeline.targets import load_targets  # noqa: E402

HAVE = "값 있음"
PRE_LISTING = "① 미상장"
REJECTED = "② rejected"
NOT_FOUND = "③ not_found"
COLLECT_FAIL = "④ 수집 실패"
NO_EVIDENCE = "⑤ 근거 없음"

ORDER = [HAVE, PRE_LISTING, REJECTED, NOT_FOUND, COLLECT_FAIL, NO_EVIDENCE]


def collect_failures() -> set[tuple[str, int]]:
    """수집 로그에서 실패한 (corp_code, bsns_year). 없으면 빈 집합."""
    p = log_dir() / "ingest_log.csv"
    if not p.exists():
        return set()
    out: set[tuple[str, int]] = set()
    with p.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if (r.get("outcome") or "").strip() == "error":
                try:
                    out.add((r["corp_code"].strip(), int(r["bsns_year"])))
                except (KeyError, ValueError):
                    continue
    return out


def build(conn) -> tuple[list[dict], Counter, list[str]]:
    targets = load_targets()
    years = list(DEFAULT_YEARS)
    fails = collect_failures()

    with conn.cursor() as cur:
        cur.execute("SELECT metric_code, name_ko, display_order FROM metric "
                    "WHERE is_active ORDER BY display_order")
        metrics = cur.fetchall()
        cur.execute("SELECT corp_code, fiscal_year, metric_code FROM company_metric")
        have = {(r[0], r[1], r[2]) for r in cur.fetchall()}
        cur.execute("SELECT corp_code, fiscal_year, metric_code, verdict FROM metric_evidence")
        verdicts = {(r[0], r[1], r[2]): r[3] for r in cur.fetchall()}

    rows: list[dict] = []
    tally: Counter = Counter()
    notes: list[str] = []

    for t in targets:
        for y in years:
            for code, label, _ in metrics:
                key = (t.corp_code, y, code)
                if not t.is_listed(y):
                    reason = PRE_LISTING
                elif key in have:
                    reason = HAVE
                elif (t.corp_code, y) in fails:
                    reason = COLLECT_FAIL
                else:
                    v = verdicts.get(key)
                    reason = {"rejected": REJECTED, "not_found": NOT_FOUND}.get(
                        v, NO_EVIDENCE if v is None else NO_EVIDENCE)
                tally[reason] += 1
                rows.append({"corp_code": t.corp_code, "display_name": t.display_name,
                             "fiscal_year": y, "metric_code": code, "reason": reason,
                             "verdict": verdicts.get(key) or ""})
                if reason not in (HAVE, PRE_LISTING):
                    notes.append(f"{t.display_name} {y} {code}  {reason}"
                                 + (f" ({verdicts.get(key)})" if verdicts.get(key) else ""))
    return rows, tally, notes


def main() -> int:
    ap = argparse.ArgumentParser(description="누락 사유 분류 리포트")
    ap.add_argument("--csv", action="store_true")
    args = ap.parse_args()

    with connect() as conn:
        rows, tally, notes = build(conn)

        total = len(rows)
        eligible = total - tally[PRE_LISTING]
        print("=" * 68)
        print("누락 사유 분류")
        print("=" * 68)
        print(f"  전체 격자        기업 10 × 연도 5 × 활성지표 6 = {total}칸")
        print(f"  − ① 미상장        {tally[PRE_LISTING]}칸  (사업보고서가 존재하지 않는 연도)")
        print(f"  ────────────────────────────────")
        print(f"  확보 대상        {eligible}칸")
        print()
        for r in ORDER:
            if r == PRE_LISTING:
                continue
            n = tally[r]
            pct = n / eligible * 100 if eligible else 0
            bar = "█" * int(pct / 3)
            print(f"  {r:<14} {n:>4}칸  {pct:>5.1f}%  {bar}")

        print("\n" + "-" * 68)
        print("지표별")
        by_metric: dict[str, Counter] = defaultdict(Counter)
        for r in rows:
            by_metric[r["metric_code"]][r["reason"]] += 1
        with conn.cursor() as cur:
            cur.execute("SELECT metric_code, name_ko FROM metric WHERE is_active "
                        "ORDER BY display_order")
            for code, label in cur.fetchall():
                c = by_metric[code]
                el = sum(c.values()) - c[PRE_LISTING]
                miss = el - c[HAVE]
                detail = ", ".join(f"{r.split()[-1] if ' ' in r else r} {c[r]}"
                                   for r in ORDER if r not in (HAVE, PRE_LISTING) and c[r])
                print(f"  {code:<18} {c[HAVE]:>2}/{el}"
                      + (f"   미확보 {miss} — {detail}" if miss else "   완전 확보"))

        if notes:
            print("\n" + "-" * 68)
            print(f"확보하지 못한 칸 전수 ({len(notes)}건)")
            for n in notes:
                print(f"  {n}")

        # 서비스 관점 — company 는 3,930 인데 지표는 10개사뿐이다
        print("\n" + "-" * 68)
        print("서비스 노출 관점 (86 발견 사항)")
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM company")
            n_company = cur.fetchone()[0]
            cur.execute("SELECT count(DISTINCT corp_code) FROM company_metric")
            n_metric = cur.fetchone()[0]
            cur.execute("""SELECT c.industry_code, i.industry_name, count(*) AS total,
                                  count(*) FILTER (WHERE EXISTS (
                                      SELECT 1 FROM company_metric m
                                       WHERE m.corp_code = c.corp_code)) AS with_metric
                             FROM company c JOIN industry i USING (industry_code)
                            WHERE c.industry_code IN (
                                  SELECT DISTINCT industry_code FROM company
                                   WHERE corp_code IN (SELECT corp_code FROM company_metric))
                            GROUP BY 1, 2 ORDER BY 1""")
            per_industry = cur.fetchall()
        print(f"  company {n_company:,}개사 중 지표 보유 {n_metric}개사 "
              f"({n_metric / n_company * 100:.2f}%)")
        # v2 의 비교 응답에는 대상 기업과 고른 peers(최대 3)만 실린다. 그래서 이 비율은
        # 비교 응답이 아니라 **후보 목록**(/api/industries/{code}/companies)의 이야기다 —
        # 목록에서 아무나 고르면 열에 아홉은 값이 전부 null 인 기업을 고르게 된다.
        print("  지표가 적재된 기업이 있는 업종 (비교 후보 목록의 모집단):")
        for ic, iname, tot, withm in per_industry:
            print(f"    KSIC {ic}  {iname[:28]:<30} {withm}/{tot}개사에 값 있음 "
                  f"→ 후보 목록의 {(tot - withm) / tot * 100:.0f}% 는 값이 전부 null")

    if args.csv:
        out = ROOT / "_out"
        out.mkdir(parents=True, exist_ok=True)
        path = out / "gaps.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\n리포트: {path}")

    print("\n① 미상장은 결측이 아니다. 분모에서 뺀 기준을 함께 읽어야 한다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

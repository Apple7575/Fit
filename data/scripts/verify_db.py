"""적재 검증 — 원천 ↔ DB (S15P21A504-84 Step 7 / F-13, F-30 부분).

    python scripts/verify_db.py
    python scripts/verify_db.py -v          # 불일치·커버리지 상세
    python scripts/verify_db.py --report    # _out/coverage.csv 도 쓴다

검사 5가지

  [1] 유일성·제약     PK 중복, verdict 값, fs_div 규칙
  [2] 원천 → DB       .cache 원본으로 정규화를 다시 돌려 DB 값과 대조
  [3] 독립 대조        정규화를 거치지 않고 원본 JSON 에서 직접 계산해 DB 와 대조
  [4] 커버리지        지표별 확보율. **상장 이전 연도는 분모에서 뺀다**
  [5] 참조 무결성     FK 고아 행, company_metric ⊆ metric_evidence

왜 [2] 와 [3] 을 나눠 두는가
--------------------------
[2] 는 정규화를 다시 돌려 비교하므로 **적재 단계**(wide→long 전개, metric_code
개명, rejected 필터, 자릿수)를 검증한다. 정규화 규칙 자체가 틀렸다면 [2] 는
통과한다 — 같은 규칙으로 두 번 계산했으니 당연히 같다.

[3] 은 정규화 코드를 전혀 쓰지 않고 원본 JSON 에서 직접 센다. 그래서 정규화
규칙까지 검증한다. 다만 **전 지표에 적용할 수는 없다** — R&D 는 8.3MB XML 의
표를 찾아야 해서 독립 구현이 파서를 다시 만드는 일이 된다. 재무·직원만 한다.

정규화 규칙 자체는 `scripts/verify_normalize.py` 가 기준선 150건으로 검증한다.
셋을 합쳐야 원천부터 DB 까지가 덮인다.

F-30 은 여기서 부분만 닫힌다
--------------------------
AC 의 3자 대조 중 **"API 노출값"은 백엔드 조회 API 가 있어야 한다.** DATA 가
닫을 수 있는 범위는 원천 ↔ DB 까지다. 나머지는 86 + 백엔드 합동 항목이다.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.collect import DEFAULT_YEARS  # noqa: E402
from pipeline.db import connect  # noqa: E402
from pipeline.normalize.runner import normalize_one  # noqa: E402
from pipeline.paths import ROOT, cache_dir  # noqa: E402
from pipeline.rawstore import RawMissing, RawStore  # noqa: E402
from pipeline.targets import load_targets  # noqa: E402

VERBOSE = "-v" in sys.argv
REPORT = "--report" in sys.argv

# CompanyYear 필드 → metric_code. load_metrics.py 의 VALUE_MAP 과 같은 대응이다
VALUE_MAP = [
    ("revenue", "revenue"), ("operating_profit", "operating_profit"),
    ("net_income", "net_income"),
    ("employee_count", "employee_count"), ("avg_salary_krw", "average_salary"),
    ("avg_tenure_years", "average_tenure"), ("rnd_ratio_pct", "rd_ratio"),
    ("rnd_cost_krw", "rd_expense"),
    ("total_liabilities", "total_liabilities"), ("total_equity", "total_equity"),
]
METRIC_ORDER = [m for _, m in VALUE_MAP]

# fs_div 를 기록하는 지표. 재무제표에서 연결/별도를 골라 온 금액만 해당한다.
# rd_expense 는 단위가 KRW 이고 카탈로그의 source_type 도 FINANCIAL_STATEMENT 지만
# **사업보고서 문서를 파싱해서 얻는다.** 연결/별도 구분 자체가 없어 NULL 이다.
# 그래서 카탈로그(unit·source_type)에서 유도하지 않고 여기 적어 둔다 — [1] 은
# 적재 코드와 독립적으로 규칙을 다시 말하는 자리다
FS_DIV_METRICS = {"revenue", "operating_profit", "net_income",
                  "total_liabilities", "total_equity"}

TOTAL_ROW = ("합계", "총계", "계", "성별합계", "전체")


def same(a, b, tol=1e-6) -> bool:
    """둘 다 없으면 일치. 하나만 없으면 불일치. 수는 상대오차로 비교."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    a, b = float(a), float(b)
    return abs(a - b) / max(abs(a), abs(b), 1.0) <= tol


# ------------------------------------------------------------------ [1] 제약

def check_constraints(conn) -> int:
    print("[1] 유일성·제약")
    bad = 0
    with conn.cursor() as cur:
        for table, key in (("company_metric", "corp_code, fiscal_year, metric_code"),
                           ("metric_evidence", "corp_code, fiscal_year, metric_code")):
            cur.execute(f"SELECT count(*) FROM (SELECT {key} FROM {table} "
                        f"GROUP BY {key} HAVING count(*) > 1) d")
            n = cur.fetchone()[0]
            bad += n
            print(f"    {table:<16} 키 중복 {n}건")

        cur.execute("""SELECT count(*) FROM metric_evidence
                        WHERE verdict NOT IN ('verified','unverified','rejected','not_found')""")
        n = cur.fetchone()[0]; bad += n
        print(f"    verdict 값 이상 {n}건")

        # 금액 지표만 fs_div 를 기록한다 (V1 주석)
        codes = sorted(FS_DIV_METRICS)
        cur.execute("""SELECT metric_code, count(*) FROM company_metric
                        WHERE (metric_code = ANY(%s) AND fs_div IS NULL)
                           OR (NOT metric_code = ANY(%s) AND fs_div IS NOT NULL)
                        GROUP BY 1 ORDER BY 1""", (codes, codes))
        viol = cur.fetchall()
        n = sum(c for _, c in viol); bad += n
        # 지표 이름을 같이 찍는다. 카탈로그에 지표가 늘었는데 이 목록을 안 고치면
        # 건수만 보고는 원인을 못 찾는다 (실제로 V7 지표 3종에서 141건이 났다)
        detail = ("  " + ", ".join(f"{m} {c}건" for m, c in viol)) if viol else ""
        print(f"    fs_div 기록 규칙 위반 {n}건{detail}")
    return bad


# ------------------------------------------------------- [2] 원천 → DB (정규화 재실행)

def check_against_source(conn, store) -> int:
    print("\n[2] 원천 → DB  (.cache 로 정규화를 다시 돌려 대조)")
    with conn.cursor() as cur:
        cur.execute("""SELECT corp_code, fiscal_year, metric_code, metric_value
                         FROM company_metric""")
        db = {(r[0], r[1], r[2]): r[3] for r in cur.fetchall()}

    checked = mismatch = 0
    for t in load_targets():
        for year in DEFAULT_YEARS:
            try:
                res = normalize_one(store, t, year)
            except Exception as e:
                print(f"    FAIL {t.display_name} {year} 정규화 예외: {e}")
                mismatch += 1
                continue
            if res.skipped:
                continue
            rejected = {e.metric_code for e in res.evidence if e.verdict == "rejected"}
            for field, code in VALUE_MAP:
                expected = getattr(res.row, field, None)
                if expected is not None and code in rejected:
                    expected = None            # rejected 는 값을 넣지 않는다
                got = db.get((t.corp_code, year, code))
                checked += 1
                if not same(expected, got):
                    mismatch += 1
                    print(f"    FAIL {t.display_name} {year} {code}: "
                          f"원천 {expected!r} != DB {got!r}")
    print(f"    {checked - mismatch}/{checked} 일치")
    return mismatch


# ---------------------------------------------- [3] 독립 대조 (정규화를 쓰지 않는다)

def _num(v) -> float | None:
    s = str(v or "").strip().replace(",", "")
    if not s or s == "-":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def check_independent(conn) -> int:
    """원본 JSON 에서 직접 계산해 DB 와 맞춘다. 정규화 코드를 쓰지 않는다."""
    print("\n[3] 독립 대조  (원본 JSON 직접 계산 — 정규화 코드 미사용)")
    cache = cache_dir()
    with conn.cursor() as cur:
        cur.execute("""SELECT corp_code, fiscal_year, metric_code, metric_value
                         FROM company_metric
                        WHERE metric_code IN ('revenue','operating_profit','net_income',
                                              'total_liabilities','total_equity',
                                              'employee_count')""")
        db = {(r[0], r[1], r[2]): r[3] for r in cur.fetchall()}

    checked = mismatch = skipped = 0
    for t in load_targets():
        for year in DEFAULT_YEARS:
            if not t.is_listed(year):
                continue

            # 재무: 주요계정에서 CFS 우선으로 직접 고른다
            p = cache / f"fnlttSinglAcnt_{t.corp_code}_{year}.json"
            if p.exists():
                rows = json.loads(p.read_text(encoding="utf-8")).get("list") or []
                # 계정명과 재무제표 구분을 여기 직접 적는다. patterns.yaml 을 읽으면
                # 정규화와 같은 규칙을 두 번 쓰는 셈이라 독립 대조가 아니게 된다
                for acc, sj, code in (("매출액", "IS", "revenue"),
                                      ("영업이익", "IS", "operating_profit"),
                                      ("당기순이익(손실)", "IS", "net_income"),
                                      ("부채총계", "BS", "total_liabilities"),
                                      ("자본총계", "BS", "total_equity")):
                    picked = None
                    for fs in ("CFS", "OFS"):        # 연결 우선, 없으면 별도
                        for r in rows:
                            if r.get("fs_div") == fs and r.get("sj_div") == sj \
                                    and r.get("account_nm") == acc:
                                picked = _num(r.get("thstrm_amount"))
                                break
                        if picked is not None:
                            break
                    got = db.get((t.corp_code, year, code))
                    if picked is None:
                        # 주요계정에 계정이 없다(카카오·크래프톤). 정규화는
                        # 전체재무제표로 폴백하므로 여기서는 대조 대상이 아니다
                        skipped += 1
                        continue
                    checked += 1
                    if not same(picked, got):
                        mismatch += 1
                        print(f"    FAIL {t.display_name} {year} {code}: "
                              f"원본 {picked!r} != DB {got!r}")

            # 직원수: 합계 행을 뺀 상세 행의 sm 합
            pe = cache / f"empSttus_{t.corp_code}_{year}.json"
            if pe.exists():
                rows = json.loads(pe.read_text(encoding="utf-8")).get("list") or []
                detail = [r for r in rows
                          if (r.get("fo_bbm") or "").strip() not in TOTAL_ROW]
                total = sum(v for v in ((_num(r.get("sm")) or
                                         (_num(r.get("rgllbr_co")) or 0) +
                                         (_num(r.get("cnttk_co")) or 0))
                                        for r in detail) if v)
                got = db.get((t.corp_code, year, "employee_count"))
                if total:
                    checked += 1
                    if not same(total, got):
                        mismatch += 1
                        print(f"    FAIL {t.display_name} {year} employee_count: "
                              f"원본 합 {total!r} != DB {got!r}")

    print(f"    {checked - mismatch}/{checked} 일치   "
          f"(주요계정에 계정이 없어 대조 제외 {skipped}건 — 정규화는 폴백으로 채웠다)")
    print("    R&D 는 8.3MB XML 파싱이 필요해 독립 구현 대상이 아니다 "
          "→ verify_normalize.py 의 기준선 150건이 담당")
    return mismatch


# -------------------------------------------------------------- [4] 커버리지

def check_coverage(conn) -> int:
    print("\n[4] 커버리지")
    targets = load_targets()
    years = list(DEFAULT_YEARS)

    # 분모 계산 — 상장 이전 연도는 애초에 대상이 아니다
    eligible = [(t.corp_code, y) for t in targets for y in years if t.is_listed(y)]
    pre_listing = [(t.corp_code, y) for t in targets for y in years if not t.is_listed(y)]
    print(f"    분모 기준: 기업 {len(targets)} x 연도 {len(years)} = {len(targets)*len(years)}건")
    print(f"              - 상장 이전 {len(pre_listing)}건 제외  →  대상 {len(eligible)}건")
    if pre_listing:
        by_corp = defaultdict(list)
        name = {t.corp_code: t.display_name for t in targets}
        for cc, y in pre_listing:
            by_corp[cc].append(y)
        for cc, ys in by_corp.items():
            lf = next(t.listed_from for t in targets if t.corp_code == cc)
            print(f"              ({name[cc]} {min(ys)}~{max(ys)} — {lf} 상장. "
                  f"사업보고서가 존재하지 않는다. '수집 실패'가 아니다)")

    with conn.cursor() as cur:
        cur.execute("""SELECT metric_code, corp_code, fiscal_year FROM company_metric""")
        have = {(r[1], r[2], r[0]) for r in cur.fetchall()}
        cur.execute("""SELECT metric_code, verdict, count(*) FROM metric_evidence
                        GROUP BY 1,2""")
        verdicts = defaultdict(Counter)
        for code, verdict, n in cur.fetchall():
            verdicts[code][verdict] = n

    rows = []
    print(f"\n    {'지표':<18}{'확보':>6}{'/':^3}{'대상':>5}{'확보율':>8}   "
          f"{'verified':>9}{'unverified':>11}{'rejected':>9}{'not_found':>10}")
    for code in METRIC_ORDER:
        got = sum(1 for cc, y in eligible if (cc, y, code) in have)
        v = verdicts[code]
        pct = got / len(eligible) * 100 if eligible else 0
        print(f"    {code:<18}{got:>6}{'/':^3}{len(eligible):>5}{pct:>7.1f}%   "
              f"{v['verified']:>9}{v['unverified']:>11}{v['rejected']:>9}{v['not_found']:>10}")
        rows.append({"metric_code": code, "확보": got, "대상": len(eligible),
                     "확보율_pct": round(pct, 1), **{k: v[k] for k in
                     ("verified", "unverified", "rejected", "not_found")}})

    if REPORT:
        out = ROOT / "_out"
        out.mkdir(parents=True, exist_ok=True)
        path = out / "coverage.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\n    리포트: {path}")
        print(f"    분모 기준 = 타깃 {len(targets)}개사 x {years[0]}~{years[-1]} "
              f"중 상장 이후 연도만 ({len(eligible)}건). 상장 이전 {len(pre_listing)}건 제외")
    return 0


# ---------------------------------------------------------- [5] 참조 무결성

def check_integrity(conn) -> int:
    print("\n[5] 참조 무결성")
    bad = 0
    with conn.cursor() as cur:
        checks = [
            ("company_metric → company 고아",
             """SELECT count(*) FROM company_metric cm
                 LEFT JOIN company c USING (corp_code) WHERE c.corp_code IS NULL"""),
            ("company_metric → metric 고아",
             """SELECT count(*) FROM company_metric cm
                 LEFT JOIN metric m USING (metric_code) WHERE m.metric_code IS NULL"""),
            ("metric_evidence → company 고아",
             """SELECT count(*) FROM metric_evidence e
                 LEFT JOIN company c USING (corp_code) WHERE c.corp_code IS NULL"""),
            ("근거 없는 값 (company_metric ⊄ metric_evidence)",
             """SELECT count(*) FROM company_metric cm
                 LEFT JOIN metric_evidence e USING (corp_code, fiscal_year, metric_code)
                 WHERE e.corp_code IS NULL"""),
        ]
        for label, sql_text in checks:
            cur.execute(sql_text)
            n = cur.fetchone()[0]
            bad += n
            print(f"    {label:<46} {n}건")
    return bad


def main() -> int:
    store = RawStore()
    with connect() as conn:
        bad = check_constraints(conn)
        bad += check_against_source(conn, store)
        bad += check_independent(conn)
        check_coverage(conn)
        bad += check_integrity(conn)

    print(f"\n{'통과' if bad == 0 else f'문제 {bad}건'}")
    print("범위: 원천 ↔ DB. 'API 노출값' 대조는 86 + 백엔드 합동 항목이다")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())

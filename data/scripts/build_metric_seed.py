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

rd_expense 는 원천이 다르다 (S15P21A504-73)
------------------------------------------
위 5종은 DART 정형 API(주요계정)에서 온다. rd_expense 는 **사업보고서 원문**을
파싱한 값이고 `staged/business_report/rd_expense.csv` 에서 읽는다. 그래서
fs_div 가 빈 칸이다 — 문서 표에는 연결·별도 구분 자체가 없다
(`scripts/verify_db.py` 의 fs_div 주석과 같은 판단).

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
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.news.csvio import write_csv  # noqa: E402
from pipeline.normalize.employee import aggregate as aggregate_employees  # noqa: E402
from pipeline.paths import cache_dir, curated_seed_dir, raw_api_dir, staged_dir  # noqa: E402

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

EMPLOYEE_METRICS = ("employee_count", "average_salary", "average_tenure")

# 보고된 1인평균급여가 (연간급여총액/인원) 과 이만큼 넘게 벌어지면 보고값을 버리고
# 총액/인원 을 쓴다. 팀 결정(2026-09-17): 50% 를 경계로 한다.
#
# 실측 분포가 근거다. 0~20% 2,093건 · 20~50% 63건까지는 계산 기준 차이이고
# (크래프톤이 12% 내외로 지속 차이 난다), 50% 위로는 성격이 다르다 — 50~90% 17건과
# 12배에 뭉친 90%+ 15건이다. 후자는 1인평균급여 칸에 **월급을 적은** 회사다.
SALARY_SWAP_GAP_PCT = 50

# E-5 상식 경계. 이 밖으로 나가는 값은 **그 지표만** 시드에서 뺀다(팀 결정 2026-09-17).
# 연 1백만원 미만은 월급 기재이거나 단위 오류이고, 10억 초과는 등기임원 표를 직원
# 표로 잘못 읽은 경우다. 총액/인원 대체(E-4)로도 안 고쳐지는 것들이라 원천이 틀렸다.
#
# "값이 있는 것보다 없는 게 낫다" — 단위 미상 R&D 를 rejected 로 버린 것과 같은
# 판단이다. 화면은 행이 없으면 지표를 접으므로 0 으로 위장되지 않는다.
SALARY_MIN = 1_000_000
SALARY_MAX = 1_000_000_000
TENURE_MAX = 45.0


def pick_salary(r) -> tuple[float | None, str]:
    """1인평균급여로 무엇을 쓸지 고른다. `(값, 사유)`.

    **검산(`verify_employees.py`)이 같은 함수를 부른다.** 여기서 고른 값이 곧 시드에
    들어가는 값이라, 규칙이 갈리면 "E-5 모순 = 시드에서 빠진 행" 이 깨진다.

    보고값과 (연간급여총액/인원) 이 크게 어긋나면 후자를 쓰되, 후자가 상식 밖이면
    보고값을 되살린다 — 두 값이 갈렸다는 것만으로 어느 쪽이 틀렸는지는 정해지지
    않는다. POSCO홀딩스 2022 는 보고값 1.14억이 맞고 총액/인원 17.8억이 틀렸다.
    """
    if (r.salary_gap_pct is None or r.salary_gap_pct < SALARY_SWAP_GAP_PCT
            or not r.avg_salary_from_total):
        return r.avg_salary_krw, ""
    for cand, why in ((r.avg_salary_from_total, "총액/인원 사용"),
                      (r.avg_salary_krw, "총액/인원이 상식 밖이라 보고값 유지")):
        if cand and _sane("average_salary", cand):
            return cand, why
    # 둘 다 상식 밖이다. 고르지 않고 넘겨 _sane 이 빼게 둔다
    return r.avg_salary_from_total, "둘 다 상식 밖"


def _sane(code: str, value: float) -> bool:
    """E-5. 시드에 넣어도 되는 값인가."""
    if code == "employee_count":
        return value > 0
    if code == "average_tenure":
        return 0 <= value <= TENURE_MAX
    if code == "average_salary":
        return SALARY_MIN <= value <= SALARY_MAX
    return True

FS_PRIORITY = ("CFS", "OFS")     # config/patterns.yaml 의 fs_div_priority

# 사업보고서 R&D 파서의 판정 중 시드에 넣을 것 (S15P21A504-73).
# high  = 3경로 교차검증이 ±0.5%p 안에서 일치
# medium= 검증 경로가 하나뿐이지만 비율이 상식 범위(0~60%) 안
# low·mismatch 는 넣지 않는다 — mismatch 는 경로끼리 어긋난 것이라 값 자체를
# 믿을 수 없고, 그런 값을 넣느니 행이 없는 편이 낫다 (팀장 기준 4항).
RD_ACCEPT_VERDICTS = ("high", "medium")

FIELDS = ["corp_code", "fiscal_year", "metric_code", "metric_value", "fs_div"]


def build_rd_rows() -> tuple[list[dict], Counter]:
    """사업보고서 파싱 결과 → rd_expense 행.

    파싱 단계가 이미 단위 미상(unit_unknown)을 버렸다. 여기서는 판정만 더 거른다.
    파일이 없으면 빈 목록이다 — 사업보고서 파싱을 안 돌린 환경에서도 나머지 5종
    시드는 그대로 나와야 한다.
    """
    src = staged_dir("business_report") / "rd_expense.csv"
    stats: Counter = Counter()
    if not src.exists():
        stats["원천 없음(parse_business_reports.py 미실행)"] = 1
        return [], stats

    out: list[dict] = []
    with src.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            stats[f"판정 {r['verdict']}"] += 1
            if r["verdict"] not in RD_ACCEPT_VERDICTS or not r["rd_expense"]:
                continue
            out.append({"corp_code": r["corp_code"],
                        "fiscal_year": int(r["fiscal_year"]),
                        "metric_code": "rd_expense",
                        "metric_value": r["rd_expense"],
                        # 문서 표에는 연결·별도 구분이 없다
                        "fs_div": ""})
    stats["채택"] = len(out)
    return out, stats


def employee_files() -> dict[tuple[str, int], Path]:
    """직원현황 원본. 전 종목은 raw/, 기존 13개사 경로는 .cache/ 에 있다.

    같은 (corp_code, year) 가 양쪽에 있으면 raw/ 를 쓴다 — 전 종목 수집이 최신이다.
    `build_curated_seed.py` 의 `_profile_files()` 와 같은 판단이고, 부문별 직원수도
    이 목록을 쓴다. **한쪽만 보면 수집을 다 돌려도 13개사에서 안 늘어난다.**
    """
    out: dict[tuple[str, int], Path] = {}
    for d in (cache_dir(), raw_api_dir()):
        for path in d.glob("empSttus_*.json"):
            parts = path.stem.split("_")
            if len(parts) != 3 or not parts[2].isdigit():
                continue
            out[(parts[1], int(parts[2]))] = path
    return out


def build_employee_rows() -> tuple[list[dict], Counter]:
    """직원현황(empSttus) → employee_count · average_salary · average_tenure.

    집계는 `pipeline/normalize/employee.py` 가 한다. 합계 행 제외, 인원 가중평균,
    급여를 상세가 아니라 합계 행에만 적는 회사(삼성전자) 분기까지 이미 검증된
    규칙이라 여기서 다시 쓰지 않는다.

    metric_code 는 카탈로그 이름이다 — 파서의 `avg_salary_krw` · `avg_tenure_years`
    가 아니라 `average_salary` · `average_tenure` 다 (V4 가 개명했고 FK 대상이다).

    fs_div 는 빈 칸이다. 직원현황에는 연결·별도 구분이 없다 — rd_expense 와 같고
    V1 주석의 "파생·비재무 지표는 NULL" 에 해당한다.

    결측은 행을 넣지 않는다(규칙 ②). 평균근속·1인평균급여를 아예 기재하지 않는
    회사가 흔하고, 그때 직원수 행은 남고 나머지 둘만 빠진다.
    """
    stats: Counter = Counter()
    files = employee_files()
    if not files:
        stats["원천 없음(collect_employees.py 미실행)"] = 1
        return [], stats

    out: list[dict] = []
    for (corp_code, year), path in sorted(files.items()):
        body = json.loads(path.read_text(encoding="utf-8"))
        rows = body.get("list") or []
        if not rows:
            # 013(미공시·상장 이전). 수집 실패와 갈라 센다
            stats["빈 응답"] += 1
            continue
        r = aggregate_employees(rows, corp_code, year)
        stats["집계한 기업-연도"] += 1

        # 1인평균급여에 **월급을 적은 회사**가 있다. 규칙은 pick_salary 에 있다
        salary, why = pick_salary(r)
        if why:
            stats[f"1인평균급여: {why}"] += 1

        for code, value in (("employee_count", r.employee_count),
                            ("average_salary", salary),
                            ("average_tenure", r.avg_tenure_years)):
            if value is None:
                stats[f"{code} 결측"] += 1
                continue
            if not _sane(code, value):
                # 지표별로 독립이다. 급여가 틀려도 인원·근속은 넣는다
                stats[f"{code} 상식 위반(E-5, 제외)"] += 1
                continue
            out.append({"corp_code": corp_code, "fiscal_year": year,
                        "metric_code": code, "metric_value": f"{value:.4f}",
                        "fs_div": ""})
        for w in r.warnings:
            # 값은 넣되 무엇이 걸렸는지는 남긴다. 3차 검증이 이걸 본다
            stats[f"경고: {w.split('(')[0].strip()[:24]}"] += 1
    return out, stats


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

    rd_rows, rd_stats = build_rd_rows()
    emp_rows, emp_stats = build_employee_rows()
    # company_metric 은 (corp_code, fiscal_year, metric_code) 가 PK 다. 원천이 달라
    # 겹칠 일이 없지만, 겹치면 적재가 아니라 여기서 걸려야 한다.
    seen = {(r["corp_code"], r["fiscal_year"], r["metric_code"]) for r in out}
    for extra, extra_stats in ((rd_rows, rd_stats), (emp_rows, emp_stats)):
        for r in extra:
            key = (r["corp_code"], r["fiscal_year"], r["metric_code"])
            if key in seen:
                extra_stats["PK 중복(건너뜀)"] += 1
                continue
            seen.add(key)
            out.append(r)

    # 적재 순서를 고정한다 — 같은 입력이면 같은 바이트여야 한다 (저장 기준 9장)
    out.sort(key=lambda r: (r["corp_code"], r["fiscal_year"], r["metric_code"]))
    return out, {"staged_rows": len(rows), "pairs": len(pairs), "used_fs": used_fs,
                 "skipped_currency": skipped_currency, "missing": missing,
                 "rd": rd_stats, "emp": emp_stats}


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
    rd = stats["rd"]
    n_rd = sum(1 for r in out if r["metric_code"] == "rd_expense")
    print(f"  rd_expense   {n_rd:,}행 (사업보고서 원문) — " +
          " · ".join(f"{k} {v}" for k, v in sorted(rd.items())))
    emp = stats["emp"]
    print(f"  직원 3종     " + " · ".join(
        f"{c} {sum(1 for r in out if r['metric_code'] == c):,}"
        for c in EMPLOYEE_METRICS) + " (직원현황)")
    print("               " + " · ".join(f"{k} {v}" for k, v in sorted(emp.items())))
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

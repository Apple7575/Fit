"""원천 데이터 정합성 검산 (S15P21A504-86 Step 4).

    python scripts/verify_source.py
    python scripts/verify_source.py -v      # 모든 차이 출력 (기본은 임계 초과분만)

**DART 가 준 값이 자기들끼리 앞뒤가 맞는지** 본다. 우리 계산이 맞는지가 아니다.

정답지가 없는 문제다 — DART 가 "삼성전자 직원 128,881명"이라고 하면 그게 맞는지
확인할 방법이 없다. 대신 **같은 사실을 두 군데서 말한 것끼리 맞춰본다.** 초등학교
검산과 같다. 정답을 몰라도 3+5=9 는 틀렸다는 걸 안다.

84 는 검산 축이 하나뿐이었다
--------------------------
    A. 상세 행 합 = 합계 행     62건 중 **14건에만** 적용 (회사가 합계 행을 안 적으면 불가)

여기서 여는 축 (합계 행이 없어도 되는 것들)

    B. 급여 교차       연간급여총액 ÷ 인원  vs  회사가 적은 1인평균     62/62
    C. 착지 ↔ 지표     dart_employee_status 상세 합  vs  employee_count
    D. 자릿수 급변      전년 대비 5배 이상 튀는가 — 단위 오류 탐지
    E. R&D 역산        rd_expense ÷ revenue × 100  vs  rd_ratio
    F. 근속 대조       상세 가중평균  vs  합계 행 (A 와 같은 제약)

기존 기록과의 관계
----------------
B 축이 찾은 것은 파이프라인이 이미 `metric_evidence.gap_pct` 에 남긴 것과
같은 기업·연도다 — 크래프톤 average_salary, NHN 2022. 독립적으로 만든 검산이
같은 곳을 짚었다는 뜻이다.

수치는 다르다. **B 는 차이가 가장 큰 사업부문 한 곳**을 보고, 파이프라인은
전사 집계를 본다. 예: NHN 2022 는 B 가 22.8%(전사 부문), gap_pct 는 18.37%다.
둘 다 맞는 값이고 보는 단위가 다르다.

**불일치를 오류로 단정하지 마라**
------------------------------
회사가 우리와 다른 방식으로 계산한 것일 수 있다. DESIGN.md 4-5장에 이미 3건이
기록되어 있다 — 한미반도체 R&D 분모, LG전자 근속 집계, 크래프톤 급여 12%.
그래서 판정을 두 단계로 나눈다.

    일치      임계 이내
    차이      임계 초과. **기록 대상이지 오류가 아니다**
    모순      물리적으로 불가능. 이것만 오류다 (인원 음수, 영업이익 > 매출 등)
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from pipeline.db import connect  # noqa: E402
from pipeline.paths import CONFIG  # noqa: E402
from pipeline.targets import load_targets  # noqa: E402


def load_known() -> dict[tuple[str, int, str], dict]:
    """확인을 마친 발견 사항. 새로 생긴 것만 실패로 세기 위한 기준선이다."""
    p = CONFIG / "known_findings.yaml"
    if not p.exists():
        return {}
    doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {(c["corp_code"], int(c["year"]), c["axis"]): c
            for c in (doc.get("contradictions") or [])}

# 임계값 — 넘으면 '차이'로 기록한다. 오류가 아니다
SALARY_GAP_PCT = 15.0      # patterns.yaml 의 salary_gap_warn_pct 와 같은 값
HEADCOUNT_GAP = 0          # 인원은 정확히 맞아야 한다
TENURE_GAP_YEARS = 0.5
# 자릿수 오류 탐지가 목적이다. 단위를 잘못 읽으면 10^3(천원)·10^6(백만원) 배가
# 난다 — SK하이닉스 R&D 를 673만원으로 읽었던 사고가 10^6 배였다.
# 5배 같은 낮은 임계는 정상적인 실적 급변까지 잡는다(2023 반도체 불황).
SPIKE_RATIO = 100.0

# 부호가 바뀔 수 있는 지표는 비율 판정에서 뺀다. 영업이익 흑자→적자는
# 정상적인 경제 현상이지 데이터 오류가 아니다.
SIGNED_METRICS = {"operating_profit"}
RND_GAP_PP = 0.5           # patterns.yaml 의 rnd_ratio_tol_pp

TOTAL_ROW_RE = r"^(성별)?(합계|총계|계)$|^전체$"


class Axis:
    """검산 축 하나. 적용 가능 건수와 결과를 함께 센다."""

    def __init__(self, code: str, name: str, unit: str, denom_label: str = ""):
        self.code, self.name, self.unit = code, name, unit
        self.denom_label = denom_label
        self.applicable = 0
        self.ok = 0
        self.diffs: list[tuple[str, str]] = []      # (대상, 설명)
        self.contradictions: list[tuple[str, str]] = []

    def pass_(self):
        self.applicable += 1
        self.ok += 1

    def diff(self, who: str, msg: str):
        self.applicable += 1
        self.diffs.append((who, msg))

    def contradiction(self, who: str, msg: str, key: tuple | None = None):
        self.applicable += 1
        self.contradictions.append((who, msg, key))

    def line(self, total: int) -> str:
        """단위가 기업-연도가 아닌 축(D)은 비율을 내지 않는다."""
        if self.denom_label:
            scope = f"적용 {self.applicable:>3}{self.denom_label:<9}"
        else:
            cov = self.applicable / total * 100 if total else 0
            scope = f"적용 {self.applicable:>3}/{total} ({cov:>4.0f}%)"
        return (f"  {self.code}. {self.name:<24} {scope}   "
                f"일치 {self.ok:>3}  차이 {len(self.diffs):>2}  "
                f"모순 {len(self.contradictions):>2}")


def pct_gap(a, b) -> Decimal:
    a, b = Decimal(a), Decimal(b)
    return abs(a - b) / max(abs(a), abs(b), Decimal(1)) * 100


def run(conn, corp_codes: set[str], names: dict[str, str], verbose: bool) -> int:
    with conn.cursor() as cur:
        cur.execute("""SELECT corp_code, bsns_year, fo_bbm, sexdstn, sm,
                              avrg_cnwk_sdytrn, fyer_salary_totamt, jan_salary_am
                         FROM dart_employee_status ORDER BY corp_code, bsns_year""")
        emp = [r for r in cur.fetchall() if r[0] in corp_codes]
        cur.execute("""SELECT corp_code, fiscal_year, metric_code, metric_value
                         FROM company_metric""")
        cm = {(r[0], r[1], r[2]): r[3] for r in cur.fetchall() if r[0] in corp_codes}

    pairs = sorted({(r[0], r[1]) for r in emp})
    total = len(pairs)
    by_pair: dict[tuple, list] = defaultdict(list)
    for r in emp:
        by_pair[(r[0], r[1])].append(r)

    import re
    is_total = re.compile(TOTAL_ROW_RE).match

    A = Axis("A", "상세 합 = 합계 행 (인원)", "명")
    B = Axis("B", "급여 교차 (총액÷인원)", "%")
    C = Axis("C", "착지 → 지표 (인원)", "명")
    F = Axis("F", "근속 상세 vs 합계 행", "년")

    for (corp, year), rows in by_pair.items():
        who = f"{names.get(corp, corp)} {year}"
        detail = [r for r in rows if not is_total((r[2] or "").strip())]
        totals = [r for r in rows if is_total((r[2] or "").strip())]

        # ── A. 상세 합 = 합계 행
        d_sum = sum(r[4] for r in detail if r[4])
        t_sum = sum(r[4] for r in totals if r[4])
        if totals and d_sum and t_sum:
            if d_sum == t_sum:
                A.pass_()
            else:
                A.diff(who, f"상세 합 {d_sum:,} vs 합계 행 {t_sum:,} "
                            f"(차 {d_sum - t_sum:+,}명)")
        # ── C. 착지 → 지표
        ec = cm.get((corp, year, "employee_count"))
        if d_sum and ec is not None:
            if int(ec) == d_sum:
                C.pass_()
            else:
                C.contradiction(who, f"착지 상세 합 {d_sum:,} vs 지표 {int(ec):,}",
                                key=(corp, year, "C"))

        # ── F. 근속 대조 (상세 인원 가중평균 vs 합계 행)
        def ten(r):
            try:
                return Decimal((r[5] or "").strip())
            except Exception:
                return None
        dw = [(ten(r), r[4]) for r in detail if ten(r) is not None and r[4]]
        tw = [(ten(r), r[4]) for r in totals if ten(r) is not None and r[4]]
        if dw and tw:
            d_avg = sum(t * n for t, n in dw) / sum(n for _, n in dw)
            t_avg = sum(t * n for t, n in tw) / sum(n for _, n in tw)
            gap = abs(d_avg - t_avg)
            if gap <= Decimal(str(TENURE_GAP_YEARS)):
                F.pass_()
            else:
                F.diff(who, f"상세 {d_avg:.2f}년 vs 합계 {t_avg:.2f}년 (차 {gap:.2f})")

    # ── B. 급여 교차 — 행 단위지만 기업-연도로 접는다
    for (corp, year), rows in by_pair.items():
        who = f"{names.get(corp, corp)} {year}"
        cand = [r for r in rows if r[6] and r[7] and r[4]]
        if not cand:
            continue
        worst = None
        for r in cand:
            derived = Decimal(r[6]) / Decimal(r[4])
            g = pct_gap(derived, r[7])
            if worst is None or g > worst[0]:
                worst = (g, r[2], derived, r[7])
        g, seg, derived, stated = worst
        if g <= Decimal(str(SALARY_GAP_PCT)):
            B.pass_()
        else:
            B.diff(who, f"[{seg}] 총액÷인원 {derived:,.0f} vs 회사 기재 {stated:,.0f} "
                        f"(차 {g:.1f}%)")

    # ── D. 자릿수 급변
    D = Axis("D", "자릿수 급변 (단위 오류 탐지)", "배", denom_label=" 연도쌍x지표")
    series: dict[tuple, dict[int, Decimal]] = defaultdict(dict)
    for (corp, year, code), v in cm.items():
        series[(corp, code)][year] = Decimal(v)
    d_units = 0
    for (corp, code), by_year in series.items():
        if code in SIGNED_METRICS:
            continue                      # 부호 전환이 정상인 지표는 제외
        ys = sorted(by_year)
        for prev, cur_y in zip(ys, ys[1:]):
            if cur_y != prev + 1:
                continue
            a, b = by_year[prev], by_year[cur_y]
            if a <= 0 or b <= 0:
                continue
            d_units += 1
            ratio = b / a
            if ratio >= Decimal(str(SPIKE_RATIO)) or ratio <= 1 / Decimal(str(SPIKE_RATIO)):
                D.contradiction(f"{names.get(corp, corp)} {prev}→{cur_y}",
                                f"{code} {a:,.0f} → {b:,.0f} ({ratio:.1f}배)",
                                key=(corp, cur_y, "D"))
            else:
                D.pass_()

    # ── E. R&D 역산
    E = Axis("E", "R&D 역산 (금액÷매출)", "%p")
    with conn.cursor() as cur:
        cur.execute("""SELECT corp_code, fiscal_year, metric_code, metric_value
                         FROM company_metric WHERE metric_code IN
                              ('rd_expense','rd_ratio','revenue')""")
        rd = {(r[0], r[1], r[2]): Decimal(r[3]) for r in cur.fetchall()
              if r[0] in corp_codes}
    for (corp, year, code) in [k for k in rd if k[2] == "rd_ratio"]:
        cost = rd.get((corp, year, "rd_expense"))
        rev = rd.get((corp, year, "revenue"))
        if cost is None or rev is None or rev <= 0:
            continue
        calc = cost / rev * 100
        stated = rd[(corp, year, "rd_ratio")]
        gap = abs(calc - stated)
        who = f"{names.get(corp, corp)} {year}"
        if gap <= Decimal(str(RND_GAP_PP)):
            E.pass_()
        else:
            E.diff(who, f"역산 {calc:.2f}% vs 적재값 {stated:.2f}% (차 {gap:.2f}%p)")

    axes = [A, B, C, D, E, F]
    print("=" * 74)
    print(f"원천 정합성 검산   기업-연도 {total}건 기준")
    print("=" * 74)
    for ax in axes:
        print(ax.line(total))

    covered = set()
    for (corp, year) in pairs:
        covered.add((corp, year))
    # 축별 적용 여부를 다시 세지 않고, 최소 1개 축이 걸린 기업-연도를 센다
    print()
    a_cov = A.applicable
    b_cov = B.applicable
    union = max(a_cov, b_cov)          # B 가 A 를 포함한다(62/62)

    # total 은 dart_employee_status 의 (기업, 연도) 수다. 착지 테이블이 비어 있는
    # 환경(적재 전 dev 등)에서는 0 이 되고, 나누면 그대로 죽는다.
    def _pct(n: int) -> str:
        return f"{n}/{total}  ({n / total * 100:.0f}%)" if total else f"{n}/0  (대상 없음)"

    print(f"  84 의 검산 가능 범위   {_pct(a_cov)}")
    print(f"  86 의 검산 가능 범위   {_pct(union)}"
          f"   ← B 축이 합계 행 없이도 걸린다")

    # 확인을 마친 발견은 실패로 세지 않는다. 늘 빨간불인 검사는 무시당하고,
    # 그러면 새로 생긴 문제도 함께 묻힌다. 숨기는 것이 아니라 계속 출력한다.
    known = load_known()
    new_con: list[str] = []
    known_con: list[str] = []
    for ax in axes:
        for who, msg, key in ax.contradictions:
            line = f"  [{ax.code}] {who}  {msg}"
            k = known.get(key) if key else None
            if k:
                known_con.append(f"{line}\n        → 확인됨: {k['id']}  ({k.get('ref', '')})")
            else:
                new_con.append(line)

    print("\n" + "-" * 74)
    print("모순 (물리적으로 불가능 — 이것만 오류다)")
    if not new_con and not known_con:
        print("  0건")
    for line in new_con:
        print(line)
    if known_con:
        print(f"\n  확인을 마친 것 {len(known_con)}건 — config/known_findings.yaml 에 등록됨")
        print("  (숨기지 않고 계속 출력한다. 실패로 세지 않을 뿐이다)")
        for line in known_con:
            print(line)
    n_con = len(new_con)

    print("\n" + "-" * 74)
    n_diff = sum(len(ax.diffs) for ax in axes)
    print(f"차이 ({n_diff}건) — 회사 기재 방식 차이일 수 있다. 기록 대상이지 오류가 아니다")
    for ax in axes:
        for who, msg in ax.diffs:
            print(f"  [{ax.code}] {who}  {msg}")

    print("\n" + "-" * 74)
    if total == 0:
        # 볼 것이 없었던 것을 통과로 보고하면 안 된다. 늘 초록불인 검사는
        # 아무도 안 보게 되고, 그러면 진짜 문제도 같이 묻힌다.
        # (verify_news.py 가 SKIP 을 PASS 로 세지 않는 것과 같은 원칙이다.)
        print("판정: 검증 못 함 — dart_employee_status 가 비어 있다")
        print("      A·B·C·E·F 축은 이 표의 (기업, 연도)를 기준으로 돈다.")
        print("      적재를 먼저 하라: load_company.py → load_raw.py → load_metrics.py")
        return 2
    if n_con == 0:
        print("판정: 새로 생긴 모순 0건"
              + (f"  (확인을 마친 {len(known_con)}건은 제외)" if known_con else ""))
    else:
        print(f"판정: 새로 생긴 모순 {n_con}건 — 확인 필요")
        print("      원인을 알아냈고 고치지 않기로 정했다면 "
              "config/known_findings.yaml 에 근거와 함께 등록하라")
    return 1 if n_con else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="원천 데이터 정합성 검산")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--all-corps", action="store_true",
                    help="타깃 10개사가 아니라 원본이 있는 13개사 전부")
    args = ap.parse_args()

    targets = load_targets()
    names = {t.corp_code: t.display_name for t in targets}
    codes = set(names)

    with connect() as conn:
        if args.all_corps:
            with conn.cursor() as cur:
                cur.execute("""SELECT c.corp_code, c.corp_name FROM company c
                                WHERE EXISTS (SELECT 1 FROM dart_employee_status e
                                               WHERE e.corp_code = c.corp_code)""")
                for cc, cn in cur.fetchall():
                    names.setdefault(cc, cn)
                    codes.add(cc)
        return run(conn, codes, names, args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())

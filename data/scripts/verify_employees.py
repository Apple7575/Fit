"""직원 지표 원천 검산 — DB·API 불필요.

`raw/opendart/api/` + `.cache/` 의 직원현황(empSttus) 원본만 읽는다. 적재를 거치지
않는 검산이 하나 있어야 적재 버그와 원천 문제를 구분할 수 있다
(`verify_financials.py` 와 같은 판단).

판정은 86번과 같이 두 단계다.

    차이   임계 초과. **기록 대상이지 오류가 아니다** (회사 기재 방식 차이일 수 있다)
    모순   물리적으로 불가능하거나 화면에 그대로 나가면 안 되는 값. 이것만 오류다

축
--
    E-1  인원 = 정규직 + 계약직                        차이 — 어느 쪽에도 안 든
                                                        직원이 있으면 정상적으로 벌어진다
    E-2  상세 행 합 = 합계 행 (인원)                   차이
    E-3  평균근속 상세 가중평균 = 합계 행               차이
    E-4  1인평균급여 vs (연간급여총액/인원)             차이 — 50% 초과는 시드가 대체한다
    E-5  상식 (인원 0 이하 · 근속 0~45년 · 급여 범위)   모순 — 시드에서 뺀다
    E-6  전년 대비 인원 10배 이상 급변                  차이 — 합병·분할이 실제로 있다

E-5 급여 범위를 1백만~10억으로 잡은 이유
---------------------------------------
연 1백만원 미만은 월급 기재이거나 단위 오류다. 10억 초과는 등기임원만 적은 표를
직원 표로 잘못 읽은 경우다. 둘 다 화면에 그대로 나가면 안 된다. **시드가 E-4 로
이미 고친 값을 검산하므로, 여기서 잡히는 것은 대체로도 못 고친 것이다.** 경계는
`build_metric_seed.SALARY_MIN` 등을 그대로 가져다 쓰므로 모순 = 시드에서 빠진 행이다.

    python scripts/verify_employees.py
    python scripts/verify_employees.py -v      # 차이도 전부 출력
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_metric_seed import (SALARY_MAX, SALARY_MIN,  # noqa: E402
                               SALARY_SWAP_GAP_PCT, TENURE_MAX, employee_files,
                               pick_salary)
from pipeline.normalize.employee import aggregate  # noqa: E402

# E-5 상식 경계는 build_metric_seed 가 들고 있다 — 시드가 실제로 거르는 값과
# 검산이 어긋나면 안 된다. 여기서 잡히는 모순은 곧 "시드에서 빠진 것" 이다.
HEADCOUNT_JUMP = 10.0        # E-6


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true", help="차이도 전부 출력한다")
    args = ap.parse_args()

    files = employee_files()
    if not files:
        print("원본이 없다 — scripts/collect_employees.py 를 먼저 돌려라")
        return 1

    gaps: Counter = Counter()
    contradictions: list[str] = []
    detail: dict[str, list[str]] = defaultdict(list)
    head_by_corp: dict[str, dict[int, float]] = defaultdict(dict)
    n_pairs = n_empty = 0

    for (corp_code, year), path in sorted(files.items()):
        rows = json.loads(path.read_text(encoding="utf-8")).get("list") or []
        if not rows:
            n_empty += 1
            continue
        n_pairs += 1
        r = aggregate(rows, corp_code, year)
        tag = f"{corp_code} {year}"

        # E-1 ~ E-3 : 파서가 이미 대조해 둔 것을 축별로 센다
        for w in r.warnings:
            if w.startswith("상세 합"):
                gaps["E-2 상세 합 != 합계 행"] += 1
                detail["E-2"].append(f"{tag} {w}")
            elif w.startswith("근속"):
                gaps["E-3 근속 상세 != 합계 행"] += 1
                detail["E-3"].append(f"{tag} {w}")
        # checks 는 **행마다** 쌓인다. 축은 기업-연도 단위로 세야 다른 축과 비교된다
        mismatched = [c for c in r.checks if c.startswith("sm(") and "!=" in c]
        if mismatched:
            gaps["E-1 인원 != 정규직+계약직"] += 1
            detail["E-1"].append(f"{tag} {mismatched[0]} (행 {len(mismatched)})")

        # E-4 : 시드가 대체하는 구간과 같은 경계를 쓴다
        if r.salary_gap_pct is not None and r.salary_gap_pct > SALARY_SWAP_GAP_PCT:
            gaps[f"E-4 1인평균급여 차이 >{SALARY_SWAP_GAP_PCT}% (시드는 총액/인원 사용)"] += 1
            detail["E-4"].append(
                f"{tag} 보고 {r.avg_salary_krw:,} vs 총액/인원 "
                f"{r.avg_salary_from_total:,} ({r.salary_gap_pct:.0f}%)")

        # E-5 : 상식. **시드와 같은 함수로 고른 값**을 본다 — 규칙이 갈리면
        # "모순 = 시드에서 빠진 행" 이 성립하지 않는다
        salary, _ = pick_salary(r)

        if r.employee_count is not None and r.employee_count <= 0:
            contradictions.append(f"{tag} E-5 인원 {r.employee_count}")
        if r.avg_tenure_years is not None and not (0 <= r.avg_tenure_years <= TENURE_MAX):
            contradictions.append(f"{tag} E-5 평균근속 {r.avg_tenure_years}년")
        if salary is not None and not (SALARY_MIN <= salary <= SALARY_MAX):
            contradictions.append(f"{tag} E-5 1인평균급여 {salary:,}원")

        if r.employee_count:
            head_by_corp[corp_code][year] = r.employee_count

    # E-6 : 연도 간 급변. 합병·분할이 실제로 있어 모순이 아니라 차이다
    for corp_code, by_year in head_by_corp.items():
        years = sorted(by_year)
        for prev, cur in zip(years, years[1:]):
            a, b = by_year[prev], by_year[cur]
            if a and b and (b / a >= HEADCOUNT_JUMP or a / b >= HEADCOUNT_JUMP):
                gaps["E-6 전년 대비 인원 10배 이상 급변"] += 1
                detail["E-6"].append(f"{corp_code} {prev}→{cur} {a:,.0f} → {b:,.0f}명")

    print(f"기업-연도 {n_pairs:,}건 검산 (빈 응답 {n_empty:,}건 제외) · "
          f"기업 {len(head_by_corp):,}")
    print("\n차이 — 기록 대상, 오류 아님")
    if gaps:
        for k, v in sorted(gaps.items()):
            print(f"  {k:52} {v:>6,}")
    else:
        print("  없음")

    print(f"\n모순 — {len(contradictions):,}건")
    for line in contradictions[:30]:
        print(f"  {line}")
    if len(contradictions) > 30:
        print(f"  … 외 {len(contradictions) - 30:,}건")

    if args.verbose:
        for axis in sorted(detail):
            print(f"\n[{axis}] {len(detail[axis]):,}건")
            for line in detail[axis][:50]:
                print(f"  {line}")
            if len(detail[axis]) > 50:
                print(f"  … 외 {len(detail[axis]) - 50:,}건")

    return 1 if contradictions else 0


if __name__ == "__main__":
    sys.exit(main())

"""직원 현황(empSttus) 집계.

초기 직원 검증 파서의 규칙을 옮겼다. 필드명·합계 라벨·임계값은
`patterns.yaml` 에서 읽는다.

집계 규칙

    직원수      Σ sm                              합계 행 제외 (더하면 2배가 된다)
    평균근속     Σ(sm x 근속) / Σ sm                인원 가중평균
    1인평균급여  Σ(sm x jan_salary_am) / Σ sm       인원 가중평균
                검증용으로 Σ fyer_salary_totamt / Σ sm 도 계산해 대조

**필드마다 소스가 다르다**는 게 핵심이다. 삼성전자는 급여를 상세 행이 아니라
합계 행에만 적는다. 인원은 상세, 급여는 합계에서 가져와야 둘 다 맞는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..patterns import Patterns, patterns as default_patterns
from .text import parse_tenure, squash, to_num


@dataclass
class EmployeeResult:
    corp_code: str
    bsns_year: int
    employee_count: int | None = None
    regular_count: int | None = None
    contract_count: int | None = None
    avg_salary_krw: int | None = None
    avg_tenure_years: float | None = None
    salary_source: str | None = None            # detail / total_rows / total_only
    avg_salary_from_total: int | None = None
    salary_gap_pct: float | None = None
    tenure_gap_years: float | None = None
    n_rows: int = 0
    n_total_rows: int = 0
    segments: list[str] = field(default_factory=list)
    rcept_no: str | None = None
    checks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _headcount(r: dict, f: dict, nulls, out: EmployeeResult):
    """행의 인원수. sm 이 없으면 정규직+계약직으로 대체한다."""
    sm = to_num(r.get(f["total"]), nulls)
    rg = to_num(r.get(f["regular"]), nulls) or 0
    cn = to_num(r.get(f["contract"]), nulls) or 0
    if sm is None:
        return rg + cn, rg, cn
    if abs(sm - (rg + cn)) > 0.5:
        out.checks.append(f"sm({sm:,.0f}) != 정규직+계약직({rg + cn:,.0f})")
    return sm, rg, cn


def _weighted(rows, field_name, getter, f, nulls, out: EmployeeResult):
    """인원 가중평균. (값, 가중치 합) 반환."""
    acc = wsum = 0.0
    for r in rows:
        sm, _, _ = _headcount(r, f, nulls, out)
        v = getter(r.get(field_name))
        if v is not None and sm:
            acc += v * sm
            wsum += sm
    return (acc / wsum, wsum) if wsum else (None, 0)


def aggregate(rows: list[dict], corp_code: str, year: int,
              p: Patterns | None = None) -> EmployeeResult:
    p = p or default_patterns()
    f = p.employee.fields
    nulls = p.employee.null_tokens
    out = EmployeeResult(corp_code=corp_code, bsns_year=year, n_rows=len(rows))

    if not rows:
        out.warnings.append("직원현황 데이터 없음")
        return out

    # 합계 행과 상세 행을 가른다. '성별합계' 표기를 쓰는 회사가 있다
    detail, totals = [], []
    for r in rows:
        seg = squash(r.get(f["segment"]))
        (totals if p.employee.total_row.match(seg) else detail).append(r)
    out.n_total_rows = len(totals)

    base = detail or totals
    if not detail and totals:
        out.salary_source = "total_only"

    for r in base:
        out.rcept_no = out.rcept_no or (squash(r.get("rcept_no")) or None)
        out.segments.append(f'{squash(r.get(f["segment"]))}/{squash(r.get(f["gender"]))}')

    # --- 인원
    head = reg = ct = 0.0
    for r in base:
        sm, rg, cn = _headcount(r, f, nulls, out)
        head += sm
        reg += rg
        ct += cn
    out.employee_count = int(head) if head else None
    out.regular_count = int(reg) if reg else None
    out.contract_count = int(ct) if ct else None

    # --- 근속 (상세 기준)
    ten, _ = _weighted(base, f["tenure"], lambda v: parse_tenure(v, nulls), f, nulls, out)
    out.avg_tenure_years = round(ten, 2) if ten is not None else None

    # --- 급여: 상세에 없으면 합계 행에서 (삼성전자)
    sal, _ = _weighted(base, f["salary_per_person"], lambda v: to_num(v, nulls), f, nulls, out)
    src = "detail" if sal is not None else None
    if sal is None and totals and base is not totals:
        sal, _ = _weighted(totals, f["salary_per_person"], lambda v: to_num(v, nulls),
                           f, nulls, out)
        src = "total_rows" if sal is not None else None
    out.avg_salary_krw = round(sal) if sal is not None else None
    out.salary_source = src or out.salary_source

    # --- 검증 1: (연간급여총액 / 인원) vs 보고된 1인평균급여
    salary_rows = totals if src == "total_rows" else base
    tot_salary = sum((to_num(r.get(f["salary_total"]), nulls) or 0) for r in salary_rows)
    tot_head = sum(_headcount(r, f, nulls, out)[0] for r in salary_rows) or head
    if tot_salary and tot_head:
        derived = tot_salary / tot_head
        out.avg_salary_from_total = round(derived)
        if out.avg_salary_krw:
            gap = abs(derived - out.avg_salary_krw) / out.avg_salary_krw * 100
            out.salary_gap_pct = round(gap, 2)
            if gap > p.thresholds.salary_gap_warn_pct:
                # 크래프톤이 12% 내외로 지속 차이가 난다. 오류가 아니라 계산 기준 차이다
                out.warnings.append(f"1인평균급여와 (총액/인원) 차이 {gap:.1f}%")

    # --- 검증 2: 합계 행이 있으면 상세 합과 대조
    if detail and totals:
        t_head = sum(_headcount(r, f, nulls, out)[0] for r in totals)
        if t_head and abs(t_head - head) > 0.5:
            out.warnings.append(f"상세 합({head:,.0f}) != 합계 행({t_head:,.0f})")
        elif t_head:
            out.checks.append(f"인원: 합계 행과 일치 ({t_head:,.0f}명)")
        t_ten, _ = _weighted(totals, f["tenure"], lambda v: parse_tenure(v, nulls),
                             f, nulls, out)
        if t_ten is not None and out.avg_tenure_years is not None:
            d = abs(t_ten - out.avg_tenure_years)
            out.tenure_gap_years = round(d, 2)
            if d > p.thresholds.tenure_gap_warn_years:
                out.warnings.append(
                    f"근속 상세({out.avg_tenure_years}) vs 합계({t_ten:.2f}) 차이 {d:.2f}년")
            else:
                out.checks.append(f"근속: 합계 행과 일치 ({t_ten:.2f}년)")

    if out.avg_tenure_years is None:
        out.warnings.append("평균근속 기재 없음")
    if out.avg_salary_krw is None:
        out.warnings.append("1인평균급여 기재 없음")
    return out

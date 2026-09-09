"""정규화 실행 — 원본 → 기업-연도 1행 + 지표별 근거.

**지표별로 독립이다.** R&D 파싱이 터져도 매출·직원은 나와야 한다. 그래서 지표
하나를 통째로 try 로 감싸고, 실패는 값이 아니라 `metric_evidence` 의 판정으로
남긴다.

산출물 두 벌

    CompanyYear       값. wide 구조를 그대로 두되, 적재는 지표 1개 = 1행인
                      develop 의 `company_metric` 으로 간다(S15P21A504-84 D-2)
    Evidence          지표별 근거·판정 (지표당 1행) → `metric_evidence`

metric_code 는 develop 의 `metric` 카탈로그 값을 쓴다 (S15P21A504-84 결정 B)
------------------------------------------------------------------------
`metric_evidence.metric_code` 가 `metric` 을 FK 로 참조하므로 파이프라인 내부
이름을 그대로 내보내면 적재가 FK 위반으로 거부된다. 실제로 확인했다.

    revenue · operating_profit · employee_count   그대로
    avg_salary_krw    → avg_salary
    avg_tenure_years  → avg_tenure
    rnd_cost_krw      → rd_expense    (V5 가 is_active=FALSE 로 추가, V17 이 rd_cost 에서 개명)
    rnd_ratio_pct     → rd_ratio

**dataclass 필드명은 바꾸지 않았다.** 회귀 기준선(tests/fixtures/normalize)이
그 이름에 묶여 있고, 바뀌는 것은 Evidence 로 나가는 문자열뿐이다.

판정 등급 매핑 (WP-6 결정, 2026-08-28)
------------------------------------
DESIGN 5장의 4종으로 접는다. 파서 원본 등급은 `evidence.raw_verdict` 에 남기므로
정보는 잃지 않는다.

    verified     교차검증 통과            매출 verified / R&D high / 직원 합계행 일치
    unverified   값은 있으나 검증 못 함    매출 conflict·single_source / R&D medium·low·mismatch
    rejected     값을 신뢰할 수 없어 버림  R&D unit_unknown / 상식 검사(sanity) 실패
    not_found    값 자체가 없음           매출 not_found / R&D no_section·no_row / 직원 결측

`unit_unknown` 을 rejected 로 둔 근거: 단위를 모르면 673만원(실제 6.7조)처럼
자릿수가 통째로 틀린 값이 나온다. 값이 있는 것보다 없는 게 낫다.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field

from ..patterns import Patterns, patterns as default_patterns
from ..rawstore import RawMissing, RawStore
from ..targets import Target
from . import employee as emp_mod
from . import revenue as rev_mod
from . import rnd as rnd_mod

log = logging.getLogger(__name__)

VERIFIED, UNVERIFIED, REJECTED, NOT_FOUND = "verified", "unverified", "rejected", "not_found"

REVENUE_VERDICT_MAP = {
    "verified": VERIFIED,
    "conflict": UNVERIFIED,
    "single_source": UNVERIFIED,
    "single_source_unmatched": UNVERIFIED,
    "not_found": NOT_FOUND,
}

RND_VERDICT_MAP = {
    "high": VERIFIED,
    "medium": UNVERIFIED,
    "low": UNVERIFIED,
    "mismatch": UNVERIFIED,
    "unit_unknown": REJECTED,
    "no_section": NOT_FOUND,
    "no_row": NOT_FOUND,
}


@dataclass
class CompanyYear:
    """company_year 테이블 1행."""
    corp_code: str
    bsns_year: int
    revenue: float | None = None
    operating_profit: float | None = None
    net_income: float | None = None
    total_liabilities: float | None = None
    total_equity: float | None = None
    fs_div: str | None = None
    employee_count: int | None = None
    regular_count: int | None = None
    contract_count: int | None = None
    avg_salary_krw: int | None = None
    avg_tenure_years: float | None = None
    rnd_cost_krw: float | None = None
    rnd_ratio_pct: float | None = None
    rcept_no: str | None = None
    source_year: int | None = None


@dataclass
class Evidence:
    """metric_evidence 테이블 1행."""
    corp_code: str
    bsns_year: int
    metric_code: str
    verdict: str
    source: str | None = None
    gap_pct: float | None = None
    evidence: dict = field(default_factory=dict)

    def as_row(self) -> dict:
        d = asdict(self)
        d["evidence"] = json.dumps(self.evidence, ensure_ascii=False)
        return d


@dataclass
class NormalizeResult:
    row: CompanyYear
    evidence: list[Evidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped: bool = False               # 상장 이전 등, 애초에 대상이 아님


def normalize_one(store: RawStore, t: Target, year: int,
                  p: Patterns | None = None) -> NormalizeResult:
    p = p or default_patterns()
    row = CompanyYear(corp_code=t.corp_code, bsns_year=year, source_year=year)
    res = NormalizeResult(row=row)

    if not t.is_listed(year):
        res.skipped = True
        res.warnings.append(f"{t.listed_from} 상장 — 해당 연도 없음")
        return res

    # 순서가 중요하다. 매출 판정은 R&D 역산(경로 D)을 상대로 쓸 수 있어서
    # R&D 파싱이 끝난 뒤에 확정된다. 값 자체는 재무 단계에서 이미 정해진다.
    fin = _do_financials(store, t, year, p, res)
    _do_employee(store, t, year, p, res)
    rnd_out = _do_rnd(store, t, year, p, res)
    _emit_revenue_evidence(t, year, p, res, fin, rnd_out)
    return res


# ------------------------------------------------------------------- 지표별

def _do_financials(store, t, year, p, res: NormalizeResult):
    """매출·영업이익 값을 채운다. 판정은 아직 내지 않는다(경로 D 대기)."""
    row = res.row
    try:
        fin = rev_mod.resolve(store, t.corp_code, year, p)
    except Exception as e:                       # 한 지표가 죽어도 나머지는 간다
        log.exception("매출 정규화 실패 %s %s", t.display_name, year)
        res.warnings.append(f"매출 정규화 예외: {e}")
        res.evidence.append(Evidence(t.corp_code, year, "revenue", NOT_FOUND,
                                     evidence={"error": str(e)}))
        return None

    row.revenue = fin.revenue
    row.operating_profit = fin.operating_profit
    row.net_income = fin.net_income.value
    row.total_liabilities = fin.total_liabilities.value
    row.total_equity = fin.total_equity.value
    row.fs_div = fin.fs_div
    row.rcept_no = fin.rcept_no
    res.warnings.extend(fin.warnings)
    return fin


def _emit_revenue_evidence(t, year, p, res: NormalizeResult, fin, rnd_out) -> None:
    """R&D 역산(경로 D)까지 반영해 매출 판정을 확정하고 근거를 남긴다."""
    if fin is None:
        return

    if rnd_out is not None and rnd_out.status == "ok":
        rev_mod.apply_backcalc(fin, rnd_out.rnd_krw, rnd_out.ratio_reported,
                               rnd_out.ratio_decimals, p)

    problem = rev_mod.sanity(fin)
    verdict = REVENUE_VERDICT_MAP.get(fin.revenue_verdict, UNVERIFIED)
    if problem and fin.revenue is not None:
        # 파싱은 됐지만 값이 말이 안 된다 → 버린다
        verdict = REJECTED
        res.warnings.append(problem)

    res.evidence.append(Evidence(
        t.corp_code, year, "revenue", verdict, source=fin.revenue_source,
        gap_pct=fin.revenue_worst_gap_pct,
        evidence={"raw_verdict": fin.revenue_verdict, "paths": fin.revenue_paths,
                  "account_nm": fin.revenue_account_nm, "fs_div": fin.fs_div,
                  "rcept_no": fin.rcept_no, "sanity": problem,
                  # 회사가 우리와 다른 분모로 비율을 계산한 흔적. 버리지 않고 기록만
                  "backcalc_gap_pct": fin.backcalc_gap_pct}))

    # 영업이익은 대조할 두 번째 경로가 없다. 값이 있어도 verified 로 올리지 않는다
    op_verdict = NOT_FOUND if fin.operating_profit is None else UNVERIFIED
    if problem and "영업이익" in problem:
        op_verdict = REJECTED
    res.evidence.append(Evidence(
        t.corp_code, year, "operating_profit", op_verdict, source=fin.revenue_source,
        evidence={"fs_div": fin.fs_div, "rcept_no": fin.rcept_no, "sanity": problem}))

    # 당기순이익·부채총계·자본총계는 매출과 같은 3경로를 갖는다(역산은 없다).
    # 매출 sanity 로 값을 버리지는 않는다 — 지분법이익·중단영업 때문에 매출보다 큰
    # 당기순이익이 실제로 나올 수 있어서 크기 비교가 판정 근거가 못 된다
    for metric_code, pick in (("net_income", fin.net_income),
                              ("total_liabilities", fin.total_liabilities),
                              ("total_equity", fin.total_equity)):
        res.evidence.append(Evidence(
            t.corp_code, year, metric_code,
            REVENUE_VERDICT_MAP.get(pick.verdict, UNVERIFIED),
            source=pick.source, gap_pct=pick.worst_gap_pct,
            evidence={"raw_verdict": pick.verdict, "paths": pick.paths,
                      "fs_div": fin.fs_div, "rcept_no": fin.rcept_no}))


def _do_employee(store, t, year, p, res: NormalizeResult) -> None:
    row = res.row
    try:
        rows = store.emp_status(t.corp_code, year)
        agg = emp_mod.aggregate(rows, t.corp_code, year, p)
    except RawMissing as e:
        res.warnings.append(str(e))
        for code in ("employee_count", "average_salary", "average_tenure"):
            res.evidence.append(Evidence(t.corp_code, year, code, NOT_FOUND,
                                         evidence={"error": "원본 없음"}))
        return
    except Exception as e:
        log.exception("직원 정규화 실패 %s %s", t.display_name, year)
        res.warnings.append(f"직원 정규화 예외: {e}")
        for code in ("employee_count", "average_salary", "average_tenure"):
            res.evidence.append(Evidence(t.corp_code, year, code, NOT_FOUND,
                                         evidence={"error": str(e)}))
        return

    row.employee_count = agg.employee_count
    row.regular_count = agg.regular_count
    row.contract_count = agg.contract_count
    row.avg_salary_krw = agg.avg_salary_krw
    row.avg_tenure_years = agg.avg_tenure_years
    row.rcept_no = row.rcept_no or agg.rcept_no
    res.warnings.extend(agg.warnings)

    # 합계 행과 대조가 성립했는지가 직원 지표의 교차검증이다
    head_checked = any("인원:" in c for c in agg.checks)
    tenure_checked = any("근속:" in c for c in agg.checks)
    base_ev = {"n_rows": agg.n_rows, "n_total_rows": agg.n_total_rows,
               "segments": agg.segments[:6], "salary_source": agg.salary_source,
               "checks": agg.checks, "warnings": agg.warnings}

    res.evidence.append(Evidence(
        t.corp_code, year, "employee_count",
        _emp_verdict(agg.employee_count, head_checked, agg.warnings),
        source=agg.salary_source, evidence=base_ev))

    res.evidence.append(Evidence(
        t.corp_code, year, "average_tenure",
        _emp_verdict(agg.avg_tenure_years, tenure_checked, agg.warnings),
        source=agg.salary_source, gap_pct=agg.tenure_gap_years, evidence=base_ev))

    # 급여는 (연간총액/인원) 과의 대조가 교차검증이다
    salary_checked = agg.salary_gap_pct is not None and \
        agg.salary_gap_pct <= p.thresholds.salary_gap_warn_pct
    res.evidence.append(Evidence(
        t.corp_code, year, "average_salary",
        _emp_verdict(agg.avg_salary_krw, salary_checked, agg.warnings),
        source=agg.salary_source, gap_pct=agg.salary_gap_pct,
        evidence={**base_ev, "avg_salary_from_total": agg.avg_salary_from_total}))


def _emp_verdict(value, cross_checked: bool, warnings: list[str]) -> str:
    if value is None:
        return NOT_FOUND
    return VERIFIED if cross_checked else UNVERIFIED


def _do_rnd(store, t, year, p, res: NormalizeResult):
    row = res.row
    if not row.rcept_no:
        res.warnings.append("rcept_no 없음 — 사업보고서를 찾을 수 없다")
        res.evidence.append(Evidence(t.corp_code, year, "rd_expense", NOT_FOUND,
                                     evidence={"error": "rcept_no 없음"}))
        return None
    try:
        path = store.document(row.rcept_no)
        out = rnd_mod.from_document(path, row.revenue, p)
    except RawMissing as e:
        res.warnings.append(str(e))
        res.evidence.append(Evidence(t.corp_code, year, "rd_expense", NOT_FOUND,
                                     evidence={"error": "원본 없음",
                                               "rcept_no": row.rcept_no}))
        return None
    except Exception as e:
        log.exception("R&D 정규화 실패 %s %s", t.display_name, year)
        res.warnings.append(f"R&D 정규화 예외: {e}")
        res.evidence.append(Evidence(t.corp_code, year, "rd_expense", NOT_FOUND,
                                     evidence={"error": str(e)}))
        return None

    verdict = RND_VERDICT_MAP.get(out.verdict, UNVERIFIED)
    if verdict != REJECTED:
        row.rnd_cost_krw = out.rnd_krw
        # 비율은 회사 보고값을 우선한다. 없으면 우리가 계산한 값
        row.rnd_ratio_pct = out.ratio_reported or out.ratio_external or out.ratio_self

    ratios = [x for x in (out.ratio_self, out.ratio_external, out.ratio_reported)
              if x is not None]
    gap = round(max(ratios) - min(ratios), 2) if len(ratios) >= 2 else None

    res.evidence.append(Evidence(
        t.corp_code, year, "rd_expense", verdict, source="doc_table", gap_pct=gap,
        evidence={"raw_verdict": out.verdict, "rcept_no": row.rcept_no,
                  "table_idx": out.table_idx, "section": out.section,
                  "unit": out.unit, "unit_src": out.unit_src,
                  "amount_raw": out.amount_raw,
                  "ratio_self": out.ratio_self, "ratio_external": out.ratio_external,
                  "ratio_reported": out.ratio_reported,
                  "consolidated_cols": out.consolidated_cols,
                  "cells": out.evidence}))

    res.evidence.append(Evidence(
        t.corp_code, year, "rd_ratio", verdict, source="doc_table", gap_pct=gap,
        evidence={"raw_verdict": out.verdict, "rcept_no": row.rcept_no,
                  "ratio_self": out.ratio_self, "ratio_external": out.ratio_external,
                  "ratio_reported": out.ratio_reported}))
    return out

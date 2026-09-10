"""`config/patterns.yaml` 로더.

이름으로 찾는 규칙은 전부 이 파일을 거친다. **코드에 계정명·라벨을 다시
적지 않는다** — 커버리지가 안 나오면 코드가 아니라 YAML 목록을 늘리는 것이 원칙
(F-27 AC1).

정규식은 로드 시점에 한 번만 컴파일한다. 65건 x 지표 4종을 도는 동안
같은 패턴을 수천 번 쓰기 때문이다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .paths import CONFIG


@dataclass(frozen=True)
class RevenuePatterns:
    names: tuple[str, ...]
    exclude: re.Pattern
    account_ids: frozenset[str]
    prefix_strip: re.Pattern


@dataclass(frozen=True)
class AccountPatterns:
    """계정명 정확일치 + XBRL 계정코드로 찾는 지표. 영업이익·당기순이익·재무상태표 계정."""
    names: tuple[str, ...]
    account_ids: frozenset[str]


@dataclass(frozen=True)
class RndPatterns:
    section_title: re.Pattern
    amount_row: re.Pattern
    amount_row_fallback: re.Pattern
    ratio_row: re.Pattern
    exclude_row: re.Pattern
    numeric_cell: re.Pattern
    revenue_row_names: tuple[str, ...]
    cell_tags: tuple[str, ...]
    units: tuple[tuple[str, int], ...]          # (표기, 배수). 긴 것부터
    unit_lookback_tables: int
    consolidated_header: str
    separate_header: str
    header_scan_rows: int


@dataclass(frozen=True)
class EmployeePatterns:
    total_row: re.Pattern
    null_tokens: frozenset[str]
    fields: dict[str, str]


@dataclass(frozen=True)
class SegmentPatterns:
    """부문별 매출 (S15P21A504-73)."""
    section_title: re.Pattern
    table_hint: re.Pattern
    exclude_row: re.Pattern
    exclude_cell: re.Pattern
    name_strip: re.Pattern
    name_max_len: int
    value_position: int


@dataclass(frozen=True)
class FacilityPatterns:
    """시설투자 (S15P21A504-73)."""
    section_title: re.Pattern
    table_hint: re.Pattern
    exclude_row: re.Pattern
    field_header: re.Pattern
    purpose_header: re.Pattern
    amount_header_priority: tuple[re.Pattern, ...]   # 순서 = 우선순위
    amount_exclude_header: re.Pattern
    foreign_currency: re.Pattern
    period_in_purpose: re.Pattern


@dataclass(frozen=True)
class TextPatterns:
    """company_text 6종의 원문 구간 (S15P21A504-73)."""
    main_business_section: re.Pattern
    main_product_section: re.Pattern
    rd_section: re.Pattern
    llm_input_chars: int
    null_tokens: re.Pattern
    product_exclude: re.Pattern


@dataclass(frozen=True)
class BusinessReportPatterns:
    segment: SegmentPatterns
    facility: FacilityPatterns
    text: TextPatterns


@dataclass(frozen=True)
class Thresholds:
    rnd_ratio_tolerance_pp: float
    rnd_ratio_min_pct: float
    rnd_ratio_max_pct: float
    revenue_path_tolerance: float
    backcalc_extra_margin: float
    backcalc_max_tolerance: float
    salary_gap_warn_pct: float
    tenure_gap_warn_years: float
    candidate_table_max_rows: int
    segment_sum_tolerance: float


@dataclass(frozen=True)
class FinancialStatement:
    fs_div_priority: tuple[str, ...]
    income_statement_div: frozenset[str]
    balance_sheet_div: frozenset[str]
    reprt_code: str


@dataclass(frozen=True)
class Patterns:
    revenue: RevenuePatterns
    operating_profit: AccountPatterns
    net_income: AccountPatterns
    total_liabilities: AccountPatterns
    total_equity: AccountPatterns
    rnd: RndPatterns
    employee: EmployeePatterns
    business_report: BusinessReportPatterns
    thresholds: Thresholds
    financial_statement: FinancialStatement


def _re(pattern: str) -> re.Pattern:
    return re.compile(pattern)


def load_patterns(path: Path | None = None) -> Patterns:
    path = path or (CONFIG / "patterns.yaml")
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))

    rev = raw["revenue"]
    op = raw["operating_profit"]
    ni = raw["net_income"]
    tl = raw["total_liabilities"]
    te = raw["total_equity"]
    rnd = raw["rnd"]
    emp = raw["employee"]
    br = raw["business_report"]
    th = raw["thresholds"]
    fs = raw["financial_statement"]

    return Patterns(
        revenue=RevenuePatterns(
            names=tuple(rev["names"]),
            exclude=_re(rev["exclude"]),
            account_ids=frozenset(rev["account_ids"]),
            prefix_strip=_re(rev["name_prefix_strip"]),
        ),
        operating_profit=AccountPatterns(
            names=tuple(op["names"]),
            account_ids=frozenset(op["account_ids"]),
        ),
        net_income=AccountPatterns(
            names=tuple(ni["names"]),
            account_ids=frozenset(ni["account_ids"]),
        ),
        total_liabilities=AccountPatterns(
            names=tuple(tl["names"]),
            account_ids=frozenset(tl["account_ids"]),
        ),
        total_equity=AccountPatterns(
            names=tuple(te["names"]),
            account_ids=frozenset(te["account_ids"]),
        ),
        rnd=RndPatterns(
            section_title=_re(rnd["section_title_re"]),
            amount_row=_re(rnd["amount_row_re"]),
            amount_row_fallback=_re(rnd["amount_row_fallback_re"]),
            ratio_row=_re(rnd["ratio_row_re"]),
            exclude_row=_re(rnd["exclude_row_re"]),
            numeric_cell=_re(rnd["numeric_cell_re"]),
            revenue_row_names=tuple(rnd["revenue_row_names"]),
            cell_tags=tuple(rnd["cell_tags"]),
            units=tuple((u["name"], int(u["multiplier"])) for u in rnd["units"]),
            unit_lookback_tables=int(rnd["unit_lookback_tables"]),
            consolidated_header=rnd["consolidated_header"],
            separate_header=rnd["separate_header"],
            header_scan_rows=int(rnd["header_scan_rows"]),
        ),
        employee=EmployeePatterns(
            total_row=_re(emp["total_row_re"]),
            null_tokens=frozenset(emp["null_tokens"]),
            fields=dict(emp["fields"]),
        ),
        business_report=BusinessReportPatterns(
            segment=SegmentPatterns(
                section_title=_re(br["segment"]["section_title_re"]),
                table_hint=_re(br["segment"]["table_hint_re"]),
                exclude_row=_re(br["segment"]["exclude_row_re"]),
                exclude_cell=_re(br["segment"]["exclude_cell_re"]),
                name_strip=_re(br["segment"]["name_strip_re"]),
                name_max_len=int(br["segment"]["name_max_len"]),
                value_position=int(br["segment"]["value_position"]),
            ),
            facility=FacilityPatterns(
                section_title=_re(br["facility"]["section_title_re"]),
                table_hint=_re(br["facility"]["table_hint_re"]),
                exclude_row=_re(br["facility"]["exclude_row_re"]),
                field_header=_re(br["facility"]["field_header_re"]),
                purpose_header=_re(br["facility"]["purpose_header_re"]),
                amount_header_priority=tuple(
                    _re(x) for x in br["facility"]["amount_header_priority_re"]),
                amount_exclude_header=_re(br["facility"]["amount_exclude_header_re"]),
                foreign_currency=_re(br["facility"]["foreign_currency_re"]),
                period_in_purpose=_re(br["facility"]["period_in_purpose_re"]),
            ),
            text=TextPatterns(
                main_business_section=_re(br["text"]["main_business_section_re"]),
                main_product_section=_re(br["text"]["main_product_section_re"]),
                rd_section=_re(br["text"]["rd_section_re"]),
                llm_input_chars=int(br["text"]["llm_input_chars"]),
                null_tokens=_re(br["text"]["null_tokens_re"]),
                product_exclude=_re(br["text"]["product_exclude_re"]),
            ),
        ),
        thresholds=Thresholds(
            rnd_ratio_tolerance_pp=float(th["rnd_ratio_tolerance_pp"]),
            rnd_ratio_min_pct=float(th["rnd_ratio_min_pct"]),
            rnd_ratio_max_pct=float(th["rnd_ratio_max_pct"]),
            revenue_path_tolerance=float(th["revenue_path_tolerance"]),
            backcalc_extra_margin=float(th["backcalc_extra_margin"]),
            backcalc_max_tolerance=float(th["backcalc_max_tolerance"]),
            salary_gap_warn_pct=float(th["salary_gap_warn_pct"]),
            tenure_gap_warn_years=float(th["tenure_gap_warn_years"]),
            candidate_table_max_rows=int(th["candidate_table_max_rows"]),
            segment_sum_tolerance=float(th["segment_sum_tolerance"]),
        ),
        financial_statement=FinancialStatement(
            fs_div_priority=tuple(fs["fs_div_priority"]),
            income_statement_div=frozenset(fs["income_statement_div"]),
            balance_sheet_div=frozenset(fs["balance_sheet_div"]),
            reprt_code=str(fs["reprt_code"]),
        ),
    )


@lru_cache(maxsize=1)
def patterns() -> Patterns:
    """기본 위치의 patterns.yaml. 프로세스당 1회만 읽는다."""
    return load_patterns()

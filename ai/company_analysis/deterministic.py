"""LLM 없이 DB 값만으로 채우는 리포트 블록.

여기서 만든 숫자는 생성 모델이 손대지 않는다. 표·KPI·차트는 전부 이 모듈이 만들고,
서술 블록도 DB 에 문장 그대로 저장된 값(main_business 등)만 그대로 옮긴다.
금액은 회사 규모에 맞춰 조원 또는 억원 한 단위로 통일해 표에 넣는다.
"""

from __future__ import annotations

from datetime import datetime

from .contracts import (
    SECTION_TITLES,
    BulletItem,
    BulletsBlock,
    ChartBlock,
    ChartSeries,
    Citation,
    CompanyReport,
    KpiBlock,
    KpiItem,
    ReportSection,
    ReportSource,
    TableBlock,
    TextBlock,
)
from .facts import (
    ACTIVITY_LABELS,
    EMPLOYEE_COUNT,
    MAIN_BUSINESS,
    MAIN_PRODUCT,
    NET_INCOME,
    NEW_BUSINESS,
    OPERATING_PROFIT,
    RD_EXPENSE,
    RD_FIELD,
    RD_RATIO,
    REVENUE,
    STRATEGY_CHANGE,
    TOTAL_ASSETS,
    TOTAL_EQUITY,
    TOTAL_LIABILITIES,
    CompanyFacts,
)

TRILLION = 1_000_000_000_000
HUNDRED_MILLION = 100_000_000
FINANCIAL_YEARS = 3
MAX_INVESTMENTS = 6
MAX_PEERS = 3
MAX_LIST_ITEMS = 8


# --- 공통 도우미 -----------------------------------------------------------


MONEY_CODES = (REVENUE, OPERATING_PROFIT, NET_INCOME, TOTAL_ASSETS, TOTAL_LIABILITIES, TOTAL_EQUITY)


def money_unit(facts: CompanyFacts) -> tuple[str, int]:
    """회사 규모로 표 단위를 정한다. 최근 연도 금액 지표 중 하나라도 1조원 이상이면 조원, 아니면 억원.

    매출액만 보면 매출 지표가 없는 금융지주(우리금융지주)가 억원으로 떨어져 자산총계가
    600만 억원처럼 읽히므로 자산·부채·자본까지 함께 본다.
    """
    year = facts.latest_year()
    if year is not None:
        for code in MONEY_CODES:
            value = facts.metric(year, code)
            if value is not None and abs(value) >= TRILLION:
                return "조원", TRILLION
    return "억원", HUNDRED_MILLION


def scale(value: float | None, divisor: int, digits: int = 1) -> float | None:
    if value is None:
        return None
    return round(value / divisor, digits)


def pct(numerator: float | None, denominator: float | None, digits: int = 1) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return round(numerator / denominator * 100, digits)


def growth(current: float | None, previous: float | None) -> float | str | None:
    """전년 대비 증감률(%). 부호가 바뀌면 흑전/적전으로 표기한다."""
    if current is None or previous is None or previous == 0:
        return None
    if previous < 0 <= current:
        return "흑전"
    if current < 0 <= previous:
        return "적전"
    return round((current - previous) / abs(previous) * 100, 1)


def metric_citation(facts: CompanyFacts, fiscal_year: int, metric_code: str) -> Citation:
    return Citation(
        source_type="COMPANY_METRIC",
        source_id=f"{facts.profile.corp_code}:{fiscal_year}:{metric_code}",
    )


def profile_citation(facts: CompanyFacts, attr_key: str, fiscal_year: int | None) -> Citation:
    suffix = f":{fiscal_year}" if fiscal_year is not None else ""
    return Citation(
        source_type="COMPANY_PROFILE",
        source_id=f"{facts.profile.corp_code}:{attr_key}{suffix}",
    )


def financial_years(facts: CompanyFacts, count: int = FINANCIAL_YEARS) -> tuple[int, ...]:
    latest = facts.latest_year()
    if latest is None:
        return ()
    return tuple(year for year in range(latest - count + 1, latest + 1) if year in facts.years())


# --- 재무 -------------------------------------------------------------------

FINANCIAL_ROWS = (
    ("매출액", REVENUE),
    ("영업이익", OPERATING_PROFIT),
    ("당기순이익", NET_INCOME),
    ("자산총계", TOTAL_ASSETS),
    ("부채총계", TOTAL_LIABILITIES),
    ("자본총계", TOTAL_EQUITY),
)


def financial_table(facts: CompanyFacts) -> TableBlock | None:
    years = financial_years(facts)
    if not years:
        return None
    unit, divisor = money_unit(facts)
    rows = []
    citations = []
    for label, code in FINANCIAL_ROWS:
        values = [scale(facts.metric(year, code), divisor) for year in years]
        if all(value is None for value in values):
            continue
        rows.append([label, *values])
        citations.extend(
            metric_citation(facts, year, code) for year in years if facts.metric(year, code) is not None
        )
    if not rows:
        return None
    return TableBlock(
        title="재무 추이",
        columns=["항목", *[f"{year}년" for year in years]],
        rows=rows,
        unit=unit,
        chart=None,
        citations=citations[:20],
    )


def ratio_table(facts: CompanyFacts) -> TableBlock | None:
    years = financial_years(facts)
    if not years:
        return None
    m = facts.metric
    rows: list[list] = []

    def add(label: str, values: list) -> None:
        if any(value is not None for value in values):
            rows.append([label, *values])

    add("영업이익률(%)", [pct(m(y, OPERATING_PROFIT), m(y, REVENUE)) for y in years])
    add("순이익률(%)", [pct(m(y, NET_INCOME), m(y, REVENUE)) for y in years])
    add("부채비율(%)", [pct(m(y, TOTAL_LIABILITIES), m(y, TOTAL_EQUITY)) for y in years])
    add("매출 성장률(%)", [growth(m(y, REVENUE), m(y - 1, REVENUE)) for y in years])
    add("영업이익 성장률(%)", [growth(m(y, OPERATING_PROFIT), m(y - 1, OPERATING_PROFIT)) for y in years])
    add("ROE(%, 기말 자본 기준)", [pct(m(y, NET_INCOME), m(y, TOTAL_EQUITY)) for y in years])
    add("R&D/매출(%)", [m(y, RD_RATIO) for y in years])
    if not rows:
        return None
    return TableBlock(
        title="산출 지표",
        columns=["지표", *[f"{year}년" for year in years]],
        rows=rows,
        citations=[metric_citation(facts, y, REVENUE) for y in years if m(y, REVENUE) is not None],
    )


def revenue_profit_chart(facts: CompanyFacts) -> ChartBlock | None:
    years = financial_years(facts)
    if not years:
        return None
    unit, divisor = money_unit(facts)
    revenue = [scale(facts.metric(y, REVENUE), divisor) for y in years]
    profit = [scale(facts.metric(y, OPERATING_PROFIT), divisor) for y in years]
    if all(v is None for v in revenue):
        return None
    return ChartBlock(
        title=f"연간 매출액 및 영업이익 추이 ({unit})",
        chart="bar",
        categories=[str(y) for y in years],
        series=[ChartSeries(name="매출액", values=revenue), ChartSeries(name="영업이익", values=profit)],
        unit=unit,
    )


def margin_chart(facts: CompanyFacts) -> ChartBlock | None:
    years = financial_years(facts)
    if not years:
        return None
    m = facts.metric
    op = [pct(m(y, OPERATING_PROFIT), m(y, REVENUE)) for y in years]
    net = [pct(m(y, NET_INCOME), m(y, REVENUE)) for y in years]
    if all(v is None for v in op):
        return None
    return ChartBlock(
        title="영업이익률 / 순이익률 추이 (%)",
        chart="line",
        categories=[str(y) for y in years],
        series=[ChartSeries(name="영업이익률", values=op), ChartSeries(name="순이익률", values=net)],
        unit="%",
    )


def kpi_block(facts: CompanyFacts) -> KpiBlock | None:
    year = facts.latest_year()
    if year is None:
        return None
    unit, divisor = money_unit(facts)
    m = facts.metric
    items: list[KpiItem] = []

    def add(label: str, code: str, value_unit: str | None, value: float | None, delta) -> None:
        if value is None:
            return
        items.append(
            KpiItem(
                label=label,
                value=value,
                unit=value_unit,
                delta_pct=delta if isinstance(delta, float) else None,
                note=delta if isinstance(delta, str) else None,
                citations=[metric_citation(facts, year, code)],
            )
        )

    add(f"{year}년 매출", REVENUE, unit, scale(m(year, REVENUE), divisor), growth(m(year, REVENUE), m(year - 1, REVENUE)))
    add(
        f"{year}년 영업이익",
        OPERATING_PROFIT,
        unit,
        scale(m(year, OPERATING_PROFIT), divisor),
        growth(m(year, OPERATING_PROFIT), m(year - 1, OPERATING_PROFIT)),
    )
    add("영업이익률", OPERATING_PROFIT, "%", pct(m(year, OPERATING_PROFIT), m(year, REVENUE)), None)
    employees = m(year, EMPLOYEE_COUNT)
    add("직원 수", EMPLOYEE_COUNT, "명", int(employees) if employees is not None else None, growth(employees, m(year - 1, EMPLOYEE_COUNT)))
    if not items:
        return None
    return KpiBlock(items=items[:6])


# --- 사업 -------------------------------------------------------------------


def intro_text(facts: CompanyFacts) -> TextBlock:
    """상단 소개. main_business 문장이 있으면 그대로, 없으면 프로필로 만든 한 문장."""
    year = facts.latest_text_year(MAIN_BUSINESS)
    sentences = facts.texts_for(MAIN_BUSINESS, year) if year is not None else ()
    if sentences:
        return TextBlock(
            text=" ".join(sentences)[:4_000],
            citations=[profile_citation(facts, MAIN_BUSINESS, year)],
        )
    p = facts.profile
    parts = [f"{p.corp_name}는"]
    if p.industry_name:
        parts.append(f"{p.industry_name}에 속한")
    parts.append("상장기업입니다.")
    if p.established_date:
        parts.append(f"{p.established_date[:4]}년에 설립되었으며")
    if p.address:
        parts.append(f"본사는 {p.address}에 있습니다.")
    return TextBlock(text=" ".join(parts), citations=[profile_citation(facts, "company", None)])


def _list_bullets(facts: CompanyFacts, attr_key: str, title: str, joiner: str | None = None) -> BulletsBlock | None:
    year = facts.latest_text_year(attr_key)
    if year is None:
        return None
    values = [v for v in facts.texts_for(attr_key, year) if v.strip()]
    if not values:
        return None
    citation = profile_citation(facts, attr_key, year)
    if joiner is not None:
        return BulletsBlock(
            title=title,
            items=[BulletItem(text=joiner.join(values)[:600], citations=[citation])],
        )
    return BulletsBlock(
        title=title,
        items=[BulletItem(text=v[:600], citations=[citation]) for v in values[:MAX_LIST_ITEMS]],
    )


def products_bullets(facts: CompanyFacts) -> BulletsBlock | None:
    return _list_bullets(facts, MAIN_PRODUCT, "주요 제품", joiner=", ")


def rnd_bullets(facts: CompanyFacts) -> BulletsBlock | None:
    return _list_bullets(facts, RD_FIELD, "연구개발 실적·분야", joiner=", ")


def new_business_bullets(facts: CompanyFacts) -> BulletsBlock | None:
    return _list_bullets(facts, NEW_BUSINESS, "신규 사업")


def strategy_bullets(facts: CompanyFacts) -> BulletsBlock | None:
    return _list_bullets(facts, STRATEGY_CHANGE, "전략 변화")


def segment_share_table(facts: CompanyFacts) -> TableBlock | None:
    """사업 부문별 매출 비중. 부문이 둘 이상일 때만 의미가 있다."""
    year = facts.latest_segment_year()
    if year is None:
        return None
    rows = facts.segment_revenue(year)
    total = sum(r.value for r in rows if r.value > 0)
    if len(rows) < 2 or total <= 0:
        return None
    unit, divisor = money_unit(facts)
    table_rows = [
        [r.segment_name, scale(r.value, divisor), pct(r.value, total)]
        for r in rows
        if r.value > 0
    ]
    return TableBlock(
        title=f"사업 부문별 매출 비중 ({year}년)",
        columns=["사업 부문", f"매출({unit})", "비중(%)"],
        rows=table_rows,
        unit=unit,
        chart="donut",
        citations=[
            Citation(source_type="SEGMENT_METRIC", source_id=f"{facts.profile.corp_code}:{year}:{r.segment_name}")
            for r in rows[:20]
        ],
    )


def investment_table(facts: CompanyFacts) -> TableBlock | None:
    """최근 투자·출자. 금액 큰 순으로 최근 연도 우선."""
    rows = [a for a in facts.activities if a.amount is not None and a.amount > 0]
    if not rows:
        return None
    rows.sort(key=lambda a: (-a.fiscal_year, -(a.amount or 0)))
    picked = rows[:MAX_INVESTMENTS]
    unit, divisor = money_unit(facts)
    table_rows = []
    for a in picked:
        target = a.counterparty or a.field_name or ACTIVITY_LABELS.get(a.activity_type, a.activity_type)
        table_rows.append(
            [
                target[:100],
                ACTIVITY_LABELS.get(a.activity_type, a.activity_type),
                scale(a.amount, divisor, 2),
                f"{a.fiscal_year}년",
                (a.purpose or "")[:100] or None,
            ]
        )
    return TableBlock(
        title="최근 투자 및 출자",
        columns=["대상", "유형", f"금액({unit})", "시기", "목적"],
        rows=table_rows,
        unit=unit,
        citations=[
            Citation(source_type="COMPANY_ACTIVITY", source_id=a.activity_id, rcept_no=a.rcept_no)
            for a in picked
        ],
    )


# --- 경쟁사 -----------------------------------------------------------------


def peer_table(facts: CompanyFacts) -> TableBlock | None:
    year = facts.latest_year()
    if year is None or not facts.peers:
        return None
    unit, divisor = money_unit(facts)
    m = facts.metric
    rows = [
        [
            facts.profile.corp_name,
            ", ".join(facts.texts_for(MAIN_PRODUCT)[:3]) or None,
            scale(m(year, REVENUE), divisor),
            pct(m(year, OPERATING_PROFIT), m(year, REVENUE)),
            int(m(year, EMPLOYEE_COUNT)) if m(year, EMPLOYEE_COUNT) is not None else None,
        ]
    ]
    for peer in facts.peers[:MAX_PEERS]:
        rows.append(
            [
                peer.corp_name,
                ", ".join(peer.main_products[:3]) or None,
                scale(peer.revenue, divisor),
                pct(peer.operating_profit, peer.revenue),
                int(peer.employee_count) if peer.employee_count is not None else None,
            ]
        )
    return TableBlock(
        title=f"동일 산업 상장사 비교 ({year}년)",
        columns=["회사명", "주요 제품", f"매출({unit})", "영업이익률(%)", "직원 수"],
        rows=rows,
        unit=unit,
        citations=[
            Citation(source_type="INDUSTRY_PEER", source_id=f"{peer.corp_code}:{peer.fiscal_year}")
            for peer in facts.peers[:MAX_PEERS]
        ],
    )


# --- 조립 -------------------------------------------------------------------


def _drop_none(blocks: list) -> list:
    return [block for block in blocks if block is not None]


def build_deterministic_report(
    facts: CompanyFacts,
    *,
    generated_at: datetime,
    sources: tuple[ReportSource, ...] = (),
) -> CompanyReport:
    """DB 값만으로 만들 수 있는 리포트. LLM 서술 블록은 이후 단계가 덧붙인다."""
    sections: list[ReportSection] = []
    warnings: list[str] = []

    # 표·KPI 를 앞에, DB 문구 목록(주요 제품·R&D·신사업·전략)은 뒤에 둔다. LLM 서술 블록은
    # 첫 표 앞에 끼워 넣으므로(narrative._merge_section) 이 순서라야 서술 → 데이터 → 부속 목록이 된다.
    business_blocks = _drop_none(
        [
            segment_share_table(facts),
            investment_table(facts),
            kpi_block(facts),
            products_bullets(facts),
            rnd_bullets(facts),
            new_business_bullets(facts),
            strategy_bullets(facts),
        ]
    )
    if business_blocks:
        sections.append(ReportSection(type="BUSINESS", title=SECTION_TITLES["BUSINESS"], blocks=business_blocks))
    else:
        warnings.append("사업 내용 섹션을 채울 확정 데이터가 없습니다.")

    financial_blocks = _drop_none(
        [financial_table(facts), ratio_table(facts), revenue_profit_chart(facts), margin_chart(facts)]
    )
    if financial_blocks:
        sections.append(
            ReportSection(type="FINANCIALS", title=SECTION_TITLES["FINANCIALS"], blocks=financial_blocks)
        )
    else:
        warnings.append("재무 분석 섹션을 채울 확정 지표가 없습니다.")

    peers = peer_table(facts)
    if peers is not None:
        sections.append(ReportSection(type="COMPETITORS", title=SECTION_TITLES["COMPETITORS"], blocks=[peers]))
    else:
        warnings.append("같은 산업의 비교 대상 상장사를 찾지 못했습니다.")

    if not sections:
        raise ValueError(f"{facts.profile.corp_name}({facts.profile.corp_code})의 리포트를 만들 데이터가 없습니다")

    latest = facts.latest_year() or facts.latest_text_year(MAIN_BUSINESS) or generated_at.year
    return CompanyReport(
        corp_code=facts.profile.corp_code,
        corp_name=facts.profile.corp_name,
        fiscal_year=latest,
        generated_at=generated_at,
        intro=intro_text(facts),
        sections=sections,
        sources=list(sources),
        warnings=warnings,
    )

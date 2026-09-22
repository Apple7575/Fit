"""리포트 생성기가 읽는 기업 사실 스냅샷.

DB(또는 시드 CSV)에서 한 기업의 확정 데이터를 한 번 읽어 불변 객체로 담는다.
생성기는 이 객체만 보고 동작하므로 DB 없이도 테스트할 수 있다.
값의 단위는 metric 카탈로그 그대로다 — KRW 는 원 단위 정수, % 는 퍼센트, YEAR 는 년.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# metric 카탈로그의 코드. 자산총계는 시드에 없어 부채총계 + 자본총계로 만든다.
REVENUE = "revenue"
OPERATING_PROFIT = "operating_profit"
NET_INCOME = "net_income"
TOTAL_LIABILITIES = "total_liabilities"
TOTAL_EQUITY = "total_equity"
TOTAL_ASSETS = "total_assets"
EMPLOYEE_COUNT = "employee_count"
AVERAGE_SALARY = "average_salary"
AVERAGE_TENURE = "average_tenure"
RD_EXPENSE = "rd_expense"
RD_RATIO = "rd_ratio"
SEGMENT_REVENUE = "segment_revenue"
SEGMENT_EMPLOYEE_COUNT = "segment_employee_count"

# company_text.attr_key
MAIN_BUSINESS = "main_business"
MAIN_PRODUCT = "main_product"
BUSINESS_KEYWORD = "business_keyword"
RD_FIELD = "rd_field"
NEW_BUSINESS = "new_business"
STRATEGY_CHANGE = "strategy_change"

# company_activity.activity_type
FACILITY = "facility"
CORPORATE_INVEST = "corporate_invest"
ACTIVITY_LABELS = {FACILITY: "시설 투자", CORPORATE_INVEST: "타법인 출자"}


@dataclass(frozen=True)
class CompanyProfile:
    corp_code: str
    corp_name: str
    industry_code: str | None
    industry_name: str | None
    induty_code: str | None
    ceo_name: str | None
    established_date: str | None
    address: str | None
    homepage_url: str | None
    stock_code: str | None


@dataclass(frozen=True)
class MetricPoint:
    fiscal_year: int
    metric_code: str
    value: float
    # CFS 연결, OFS 별도, None 은 구분 없음(직원·R&D 등).
    fs_div: str | None


@dataclass(frozen=True)
class SegmentPoint:
    fiscal_year: int
    segment_name: str
    metric_code: str
    value: float


@dataclass(frozen=True)
class Activity:
    activity_id: str
    fiscal_year: int
    activity_type: str
    field_name: str | None
    purpose: str | None
    amount: float | None
    rcept_no: str | None
    counterparty: str | None


@dataclass(frozen=True)
class TextAttr:
    fiscal_year: int
    attr_key: str
    seq: int
    value: str


@dataclass(frozen=True)
class PeerFacts:
    """같은 산업(KSIC 대분류) 상장사 한 곳의 최신 연도 핵심 지표."""

    corp_code: str
    corp_name: str
    fiscal_year: int
    revenue: float | None
    operating_profit: float | None
    net_income: float | None
    employee_count: float | None
    main_products: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompanyFacts:
    profile: CompanyProfile
    metrics: tuple[MetricPoint, ...] = ()
    segments: tuple[SegmentPoint, ...] = ()
    activities: tuple[Activity, ...] = ()
    texts: tuple[TextAttr, ...] = ()
    peers: tuple[PeerFacts, ...] = ()
    _index: dict[tuple[int, str], float] = field(default_factory=dict, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        index: dict[tuple[int, str], float] = {}
        # 연결(CFS)을 우선하고, 없으면 별도(OFS)·구분 없음을 쓴다.
        priority = {"CFS": 0, None: 1, "": 1, "OFS": 2}
        best: dict[tuple[int, str], int] = {}
        for point in self.metrics:
            key = (point.fiscal_year, point.metric_code)
            rank = priority.get(point.fs_div, 3)
            if key not in best or rank < best[key]:
                best[key] = rank
                index[key] = point.value
        for year in {point.fiscal_year for point in self.metrics}:
            liabilities = index.get((year, TOTAL_LIABILITIES))
            equity = index.get((year, TOTAL_EQUITY))
            if (year, TOTAL_ASSETS) not in index and liabilities is not None and equity is not None:
                index[(year, TOTAL_ASSETS)] = liabilities + equity
        object.__setattr__(self, "_index", index)

    # --- 조회 도우미 -------------------------------------------------------

    def metric(self, fiscal_year: int, metric_code: str) -> float | None:
        return self._index.get((fiscal_year, metric_code))

    def years(self) -> tuple[int, ...]:
        """지표가 하나라도 있는 연도, 오름차순."""
        return tuple(sorted({year for year, _ in self._index}))

    def latest_year(self) -> int | None:
        """매출액이 있는 가장 최근 연도. 없으면 지표가 있는 최근 연도."""
        with_revenue = [year for year, code in self._index if code == REVENUE]
        if with_revenue:
            return max(with_revenue)
        years = self.years()
        return years[-1] if years else None

    def texts_for(self, attr_key: str, fiscal_year: int | None = None) -> tuple[str, ...]:
        """attr_key 의 값들을 seq 순으로. 연도를 주지 않으면 그 키의 최신 연도를 쓴다."""
        rows = [row for row in self.texts if row.attr_key == attr_key]
        if not rows:
            return ()
        year = fiscal_year if fiscal_year is not None else max(row.fiscal_year for row in rows)
        return tuple(row.value for row in sorted(rows, key=lambda r: r.seq) if row.fiscal_year == year)

    def latest_text_year(self, attr_key: str) -> int | None:
        years = [row.fiscal_year for row in self.texts if row.attr_key == attr_key]
        return max(years) if years else None

    def segment_revenue(self, fiscal_year: int) -> tuple[SegmentPoint, ...]:
        return tuple(
            sorted(
                (
                    row
                    for row in self.segments
                    if row.fiscal_year == fiscal_year and row.metric_code == SEGMENT_REVENUE
                ),
                key=lambda r: -r.value,
            )
        )

    def latest_segment_year(self) -> int | None:
        years = [row.fiscal_year for row in self.segments if row.metric_code == SEGMENT_REVENUE]
        return max(years) if years else None

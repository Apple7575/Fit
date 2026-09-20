"""표준 지표 질문의 결정적 처리.

"NAVER의 2025년 부채비율은?" 같은 질문은 답이 `company_metric` 확정값 하나로 정해진다. 모델이 원문 표에서
다른 정의(소수 비율 0.29)나 다른 연도(FY'24) 값을 골라 오답이 난 실측 사례가 있어, 이런 질문은
① 질문에서 지표와 연도를 읽고 ② 모델 답의 숫자를 확정값과 대조하고 ③ 어긋나면 모델 답을 버리고
확정값으로 정해진 문장을 답한다. 확정값이 없는 연도는 있는 연도를 알려 주며 정직하게 회피한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .contracts import Citation
from .deterministic import metric_citation, money_unit, pct, scale
from .facts import (
    EMPLOYEE_COUNT,
    NET_INCOME,
    OPERATING_PROFIT,
    REVENUE,
    TOTAL_ASSETS,
    TOTAL_EQUITY,
    TOTAL_LIABILITIES,
    CompanyFacts,
)

# 파생 지표 코드. facts 에는 없고 두 확정값으로 계산한다.
OPERATING_MARGIN = "operating_margin"
NET_MARGIN = "net_margin"
DEBT_RATIO = "debt_ratio"
ROE = "roe"

# (정규식, 코드, 표시 이름, 종류). 긴 이름이 먼저 와야 "영업이익률" 이 "영업이익" 으로 잡히지 않는다.
_METRIC_PATTERNS: tuple[tuple[re.Pattern[str], str, str, str], ...] = (
    (re.compile(r"영업\s*이익률"), OPERATING_MARGIN, "영업이익률", "pct"),
    (re.compile(r"(?:당기)?\s*순\s*이익률"), NET_MARGIN, "순이익률", "pct"),
    (re.compile(r"부채\s*비율"), DEBT_RATIO, "부채비율", "pct"),
    (re.compile(r"\bROE\b|자기\s*자본\s*이익률", re.I), ROE, "ROE", "pct"),
    (re.compile(r"영업\s*이익"), OPERATING_PROFIT, "영업이익", "money"),
    (re.compile(r"(?:당기)?\s*순\s*이익|순손익|당기\s*순\s*손실"), NET_INCOME, "당기순이익", "money"),
    (re.compile(r"매출\s*액|매출(?!\s*(?:비중|구성|성장|증가|감소|추이))"), REVENUE, "매출액", "money"),
    (re.compile(r"자산\s*총계|총\s*자산"), TOTAL_ASSETS, "자산총계", "money"),
    (re.compile(r"부채\s*총계|총\s*부채"), TOTAL_LIABILITIES, "부채총계", "money"),
    (re.compile(r"자본\s*총계|총\s*자본|자기\s*자본(?!\s*이익률)"), TOTAL_EQUITY, "자본총계", "money"),
    (re.compile(r"(?:임\s*)?직원\s*수|직원(?:은|이|들은)?\s*(?:몇|얼마)|종업원\s*수|임직원(?:은|이)?\s*(?:몇|얼마)"), EMPLOYEE_COUNT, "직원 수", "count"),
)

# 여러 값을 한꺼번에 묻거나 흐름을 묻는 질문은 모델 서술에 맡긴다.
_NOT_SINGLE_FACT = re.compile(r"추이|변화|흐름|성장률|증감|비교|대비|왜|이유|원인|어떻게\s*(?:변|달라)|년\s*(?:부터|간|동안)|최근\s*\d\s*년")
_YEAR = re.compile(r"(20\d{2})\s*(?:년|연도|년도|사업연도|회계연도|기)?")

MONEY_TOLERANCE = 0.005
COUNT_TOLERANCE = 0.0005
PCT_TOLERANCE = 0.15


@dataclass(frozen=True)
class MetricQuery:
    code: str
    label: str
    kind: str  # money | count | pct
    fiscal_year: int
    year_in_question: bool


@dataclass(frozen=True)
class MetricAnswer:
    text: str
    citations: list[Citation]
    matched: bool  # True 면 확정값이 있어 답을 만들었고, False 면 회피 문장이다


def detect_metric_query(question: str, facts: CompanyFacts) -> MetricQuery | None:
    """질문이 표준 지표 하나를 묻는지 판단한다. 아니면 None."""
    if _NOT_SINGLE_FACT.search(question):
        return None
    found: list[tuple[str, str, str]] = []
    remaining = question
    for pattern, code, label, kind in _METRIC_PATTERNS:
        if pattern.search(remaining):
            found.append((code, label, kind))
            remaining = pattern.sub(" ", remaining)
    if len(found) != 1:
        return None
    code, label, kind = found[0]
    years = {int(m.group(1)) for m in _YEAR.finditer(question)}
    if len(years) > 1:
        return None
    if years:
        return MetricQuery(code, label, kind, years.pop(), True)
    latest = facts.latest_year()
    if latest is None:
        return None
    return MetricQuery(code, label, kind, latest, False)


def expected_value(facts: CompanyFacts, query: MetricQuery) -> float | None:
    """확정값. money 는 원, count 는 명, pct 는 %."""
    m = facts.metric
    y = query.fiscal_year
    if query.code == OPERATING_MARGIN:
        return pct(m(y, OPERATING_PROFIT), m(y, REVENUE))
    if query.code == NET_MARGIN:
        return pct(m(y, NET_INCOME), m(y, REVENUE))
    if query.code == DEBT_RATIO:
        return pct(m(y, TOTAL_LIABILITIES), m(y, TOTAL_EQUITY))
    if query.code == ROE:
        return pct(m(y, NET_INCOME), m(y, TOTAL_EQUITY))
    return m(y, query.code)


def _source_codes(query: MetricQuery) -> tuple[str, ...]:
    return {
        OPERATING_MARGIN: (OPERATING_PROFIT, REVENUE),
        NET_MARGIN: (NET_INCOME, REVENUE),
        DEBT_RATIO: (TOTAL_LIABILITIES, TOTAL_EQUITY),
        ROE: (NET_INCOME, TOTAL_EQUITY),
    }.get(query.code, (query.code,))


# --- 답에서 숫자 읽기 ------------------------------------------------------------

_MONEY_PHRASE = re.compile(
    r"(?P<sign>-|−|마이너스\s*)?"
    r"(?:(?P<a>\d+(?:\.\d+)?)\s*조(?:\s*(?P<b>\d{1,3}(?:,\d{3})*)\s*억)?\s*원?"  # 97.1조원 / 97조 1,468억원
    r"|(?P<c>\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*억\s*원?"  # 1,121억원
    r"|(?P<d>\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?P<u>백만|천만|십억|천)\s*원)"  # 22,133백만원
)
_SCALE = {"백만": 1_000_000, "천만": 10_000_000, "십억": 1_000_000_000, "천": 1_000}


def money_values_in(text: str) -> list[float]:
    """답에 나온 금액을 원 단위로. 97.1조원·97조 1,468억원·97,146,675백만원은 모두 같은 값이다."""
    values: list[float] = []
    for m in _MONEY_PHRASE.finditer(text):
        if m.group("a"):
            value = float(m.group("a")) * 1_000_000_000_000
            if m.group("b"):
                value += float(m.group("b").replace(",", "")) * 100_000_000
        elif m.group("c"):
            value = float(m.group("c").replace(",", "")) * 100_000_000
        else:
            value = float(m.group("d").replace(",", "")) * _SCALE[m.group("u")]
        values.append(-value if m.group("sign") else value)
    return values


def _relative_close(found: float, expected: float, tolerance: float) -> bool:
    return expected != 0 and abs(found - expected) / abs(expected) <= tolerance


def answer_matches(answer: str, query: MetricQuery, expected: float) -> bool:
    """모델 답에 확정값과 같은 숫자가 하나라도 있으면 통과."""
    if query.kind == "money":
        # 리포트 표는 조원·억원 소수 첫째 자리로 반올림해 보여 준다(2,020,287,132,255원 → 2.0조원).
        # 그 표기를 그대로 옮긴 답도 정답이므로 반올림된 값 자체는 오차 없이 허용한다.
        rounded = {round(expected / d, 1) * d for d in (1_000_000_000_000, 100_000_000)}
        return any(
            _relative_close(v, expected, MONEY_TOLERANCE) or any(_relative_close(v, r, 1e-9) for r in rounded)
            for v in money_values_in(answer)
        )
    if query.kind == "count":
        numbers = [float(n.replace(",", "")) for n in re.findall(r"\d{1,3}(?:,\d{3})+|\d+", answer)]
        return any(_relative_close(n, expected, COUNT_TOLERANCE) for n in numbers)
    numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?(?=\s*%)", answer)]
    return any(abs(n - expected) <= PCT_TOLERANCE for n in numbers)


# --- 확정값으로 답 만들기 ----------------------------------------------------------


def format_value(facts: CompanyFacts, query: MetricQuery, value: float) -> str:
    if query.kind == "money":
        unit, divisor = money_unit(facts)
        scaled = scale(value, divisor)
        return f"{scaled:,.1f}{unit}"
    if query.kind == "count":
        return f"{int(round(value)):,}명"
    return f"{value:.1f}%"


def deterministic_answer(facts: CompanyFacts, query: MetricQuery) -> MetricAnswer:
    """확정값이 있으면 정해진 문장, 없으면 있는 연도를 알려 주는 회피 문장."""
    name = facts.profile.corp_name
    value = expected_value(facts, query)
    if value is None:
        years = [y for y in facts.years() if expected_value(facts, MetricQuery(query.code, query.label, query.kind, y, True)) is not None]
        if years:
            span = f"{years[0]}년~{years[-1]}년" if len(years) > 1 else f"{years[0]}년"
            text = f"{name}의 {query.fiscal_year}년 {query.label}은 확정 지표에 없습니다. 확정 지표는 {span} 값만 있습니다."
        else:
            text = f"{name}의 {query.label}은 확정 지표에 없어 답할 수 없습니다."
        return MetricAnswer(text, [], matched=False)
    text = f"{name}의 {query.fiscal_year}년 {query.label}은 {format_value(facts, query, value)}입니다. 공시 확정 지표(연결 우선) 기준입니다."
    citations = [metric_citation(facts, query.fiscal_year, code) for code in _source_codes(query) if facts.metric(query.fiscal_year, code) is not None]
    return MetricAnswer(text, citations, matched=True)

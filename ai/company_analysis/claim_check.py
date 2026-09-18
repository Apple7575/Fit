"""서술 문장의 숫자를 인용 근거와 결정적으로 대조한다.

기존 기업분석 실험(company_context)에서 옮겨 왔다. 나노솔루션 v3 는 `판매경로별 매출액` 표의
`4,452,074` 를 `4,452,074 단위 판매` 로 썼고 프롬프트로는 막히지 않았다. 그래서 생성 뒤에
문장 단위로 검사해 위반 문장을 버린다.

검사 대상은 천 단위 쉼표가 있거나 다섯 자리 이상인 "금액형" 숫자, 그리고 소수·퍼센트다.
연도(4자리)와 작은 개수는 검사하지 않는다. 통과가 의미상 정확함을 보증하지는 않는다 —
근거 부족을 증명하는 방향으로만 동작한다.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

# 4,452,074 / 12,345.6 / 112078954483 처럼 금액으로 읽힐 수 있는 숫자.
_AMOUNT_TOKEN = re.compile(r"(?<![\d,.])(?:\d{1,3}(?:,\d{3})+|\d{5,})(?:\.\d+)?(?![\d,])")
# 48.6% / 46.8 처럼 소수가 있는 비율. 정수 퍼센트(57%)도 포함한다.
_RATIO_TOKEN = re.compile(r"(?<![\d,.])\d{1,4}(?:\.\d+)?(?=\s*%)")
_NEXT_TOKEN_WINDOW = 8

_MONEY_UNITS = ("원", "천원", "백만원", "억원", "천만원", "십억원", "조원", "USD", "달러", "$")
_MONEY_UNIT_AFTER = re.compile(r"^\s*(?:천|백만|억|천만|십억|조)?\s*원|^\s*(?:USD|달러|\$)")
_QUANTITY_AFTER = re.compile(
    r"^\s*(?:단위|개|대|톤|t|kg|㎏|g|매|장|건|명|주|본|세트|set|ea|EA|박스|리터|L|㎡|평|회)(?![가-힣A-Za-z])"
    r"|^\s*(?:단위가|단위를|단위의|개가|개를|대가|대를|톤이|톤을)"
)
_SKIP_AFTER = re.compile(r"^\s*(?:%|퍼센트|년|월|일|분기|차|호|번|기|층|회차)")
# `43,0백만원` 처럼 천 단위 묶음이 세 자리가 아닌 숫자. 잘린 표를 읽고 만든 가짜 숫자의 흔적.
_MALFORMED_GROUPING = re.compile(r"(?<![\d,.])\d{1,3}(?:,\d{3})*,\d{1,2}(?![\d,])")


@dataclass(frozen=True)
class CitedText:
    """검사용 근거 한 건. 표면 content_type 이 TABLE 이고 unit 이 금액 단위일 수 있다."""

    evidence_id: str
    content: str
    is_table: bool = False
    unit: str | None = None
    header: str = ""


@dataclass(frozen=True)
class Violation:
    code: str
    detail: str


def _digits_present(number: str, content: str) -> bool:
    # 디에이피 v1: 표의 `543,196,074` 를 `543,196천원` 으로 썼다. 앞부분 부분 일치는 인정하지 않는다.
    if re.search(rf"(?<![\d,.]){re.escape(number)}(?![\d,]|\.\d)", content):
        return True
    plain = number.replace(",", "")
    return bool(re.search(rf"(?<![\d,.]){re.escape(plain)}(?![\d,]|\.\d)", content.replace(",", "")))


def is_money_table(row: CitedText) -> bool:
    if not row.is_table:
        return False
    if row.unit and row.unit.strip() in _MONEY_UNITS:
        return True
    return bool(re.search(r"매출액|매출|금액|영업이익|순이익|자산|부채|자본|비용|원가|투자액|수주", row.header))


def _ratio_present(token: str, rows: Iterable[CitedText]) -> bool:
    for row in rows:
        if re.search(rf"(?<![\d.]){re.escape(token)}(?![\d])", row.content):
            return True
    return False


def numeric_claim_violations(text: str, cited: Iterable[CitedText]) -> list[Violation]:
    """빈 목록이면 결정적 검사를 통과했다. 인용 근거가 없으면 숫자가 있는 문장은 전부 위반이다."""
    cited = list(cited)
    violations: list[Violation] = []
    for match in _MALFORMED_GROUPING.finditer(text):
        violations.append(Violation("malformed_number", f"천 단위 묶음이 깨진 숫자 {match.group(0)}"))

    seen: set[str] = set()
    for match in _AMOUNT_TOKEN.finditer(text):
        number = match.group(0)
        after = text[match.end(): match.end() + _NEXT_TOKEN_WINDOW]
        if _SKIP_AFTER.match(after) or number in seen:
            continue
        seen.add(number)
        holders = [row for row in cited if _digits_present(number, row.content)]
        if not holders:
            violations.append(Violation("number_not_in_evidence", f"인용 근거에 없는 숫자 {number}"))
            continue
        if not all(is_money_table(row) for row in holders):
            continue
        if _QUANTITY_AFTER.match(after):
            violations.append(Violation("amount_as_quantity", f"금액 표의 숫자 {number}를 수량으로 서술: '{number}{after.strip()}'"))
            continue
        if not _MONEY_UNIT_AFTER.match(after):
            violations.append(Violation("money_unit_missing", f"금액 표의 숫자 {number}에 금액 단위가 없음"))
            continue
        expected = {row.unit.strip() for row in holders if row.unit and row.unit.strip() in _MONEY_UNITS}
        if expected and not any(_unit_follows(after, unit) for unit in expected):
            violations.append(
                Violation("unit_mismatch", f"숫자 {number}의 단위가 표 단위 {'/'.join(sorted(expected))}와 다름: '{number}{after.strip()}'")
            )

    for match in _RATIO_TOKEN.finditer(text):
        token = match.group(0)
        if token in seen:
            continue
        seen.add(token)
        if not _ratio_present(token, cited):
            violations.append(Violation("ratio_not_in_evidence", f"인용 근거에 없는 비율 {token}%"))

    # 97.1조원 / 34,549명 / 6.9배 처럼 단위가 바로 붙은 작은 숫자. 확정 지표 표는 조원·억원으로
    # 줄인 소수를 담으므로 위의 금액형 규칙에 걸리지 않는다. 근거에 같은 숫자가 있어야 한다.
    for match in _UNIT_NUMBER.finditer(text):
        token = match.group(1)
        if token in seen or re.fullmatch(r"(?:19|20)\d{2}", token):
            continue
        seen.add(token)
        if not _ratio_present(token, cited):
            violations.append(Violation("number_not_in_evidence", f"인용 근거에 없는 숫자 {token}{match.group(2)}"))
    return violations


_UNIT_NUMBER = re.compile(
    r"(?<![\d,.])(\d{1,4}(?:,\d{3})*(?:\.\d+)?)\s*(조\s*원|억\s*원|백만\s*원|천\s*원|만\s*원|명|배|개사|건|년\s*연속)"
)


_SHARE_WORD = re.compile(r"점유율|시장\s*점유|M/S|share", re.I)


def share_claim_violations(text: str, cited: Iterable[CitedText]) -> list[Violation]:
    """'점유율' 문장의 퍼센트는 '점유율' 을 말하는 근거 안에 있어야 한다.

    SK하이닉스 v3: 시장 구성 비율("DRAM 이 메모리 시장의 65%")을 회사 점유율 65% 로 썼다. 숫자는 근거에
    있으므로 숫자 검사는 통과한다. 그래서 점유율 문장은 점유율 근거만 인정한다.
    """
    if not _SHARE_WORD.search(text):
        return []
    share_rows = [row for row in cited if _SHARE_WORD.search(row.content)]
    violations: list[Violation] = []
    for match in _RATIO_TOKEN.finditer(text):
        token = match.group(0)
        if not _ratio_present(token, share_rows):
            violations.append(Violation("share_not_in_evidence", f"점유율 {token}% 를 말하는 근거가 없음"))
    return violations


def _unit_follows(after: str, unit: str) -> bool:
    pattern = r"\s*".join(re.escape(ch) for ch in unit)
    return re.match(rf"^\s*{pattern}", after) is not None

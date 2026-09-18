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
    # 표의 소속 법인(자회사 등). 이 표의 숫자를 쓰는 문장은 이 이름을 밝혀야 한다.
    scope: str | None = None


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


def _table_rows_text(row: CitedText) -> str:
    """표 조각에서 머리글 아래 행들만. 캡션(표 위 설명 문장)은 자기 단위를 가진 문장이라 표 단위와 무관하다."""
    lines = row.content.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("표 머리글:"):
            return "\n".join(lines[index:])
    return row.content


def _in_table_rows(number: str, row: CitedText) -> bool:
    return row.is_table and _digits_present(number, _table_rows_text(row))


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
        # 원문에서 숫자 바로 뒤에 붙은 금액 단위가 있으면 답도 같은 단위여야 한다("3,472억원" → "3,472백만원" 금지).
        source_units = _source_money_units(number, holders)
        written = _WRONG_UNIT_AFTER.match(after)
        if source_units and written and written.group(1).replace(" ", "") not in source_units:
            correct = "/".join(sorted(source_units))
            violations.append(
                Violation("unit_mismatch", f"숫자 {number}의 단위가 원문 단위 {correct}와 다름: '{number}{after.strip()}' → '{number}{correct}' 로 쓴다")
            )
            continue
        # 표 조각이라도 숫자가 캡션 문장에만 있으면(동양생명보험 "총자산 35조 3,472억원" 캡션, 표 단위 백만원)
        # 그 문장의 단위가 맞고 표 단위 규칙은 적용하지 않는다.
        if not all(is_money_table(row) and _in_table_rows(number, row) for row in holders):
            continue
        # 금액 표 안의 글 셀에 "2,048개 I/O" 처럼 수량이 적혀 있을 수 있다(SK하이닉스 연구개발 실적 표, 단위 백만원).
        # 모델이 숫자를 뒤따르는 단위까지 그대로 옮겼으면 금액 규칙을 적용하지 않는다.
        if _verbatim_with_unit(number, after, holders):
            continue
        if _QUANTITY_AFTER.match(after):
            violations.append(Violation("amount_as_quantity", f"금액 표의 숫자 {number}를 수량으로 서술: '{number}{after.strip()}'"))
            continue
        if not _MONEY_UNIT_AFTER.match(after):
            violations.append(Violation("money_unit_missing", f"금액 표의 숫자 {number}에 금액 단위가 없음"))
            continue
        expected = {row.unit.strip() for row in holders if row.unit and row.unit.strip() in _MONEY_UNITS}
        if expected and not any(_unit_follows(after, unit) for unit in expected):
            correct = "/".join(sorted(expected))
            violations.append(
                Violation(
                    "unit_mismatch",
                    f"숫자 {number}의 단위가 표 단위 {correct}와 다름: '{number}{after.strip()}' → '{number}{correct}' 로 쓴다",
                )
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


_UNIT_WORD_AFTER = re.compile(r"^\s*([A-Za-z가-힣%㎡㎏]{1,6})")


def _verbatim_with_unit(number: str, after: str, holders: Iterable[CitedText]) -> bool:
    """`숫자 + 바로 뒤 단위 낱말` 이 근거에 그대로 있으면 True. 금액 단위(원)는 제외한다."""
    match = _UNIT_WORD_AFTER.match(after)
    if not match:
        return False
    unit = match.group(1)
    if unit.endswith("원") or unit in ("USD", "달러"):
        return False
    needle = re.sub(r"\s+", "", f"{number}{unit}")
    return any(needle in re.sub(r"\s+", "", row.content) for row in holders)


# --- 소속 법인 ------------------------------------------------------------------

_ENTITY_SUFFIX = re.compile(
    r"(?:은행|증권|카드|보험|생명|화재|캐피탈|자산운용|운용|신탁|저축은행|금융|투자|파트너스|홀딩스|지주|"
    r"에프아이에스|에프앤아이|종합금융|벤처|리츠|㈜|주식회사|\(주\)|Inc\.?|Ltd\.?|Co\.|Corp\.?|LLC)$",
    re.I,
)
_NOT_ENTITY = re.compile(r"\d|업무|결과|정의|추이|잔액|비용|현황|체계|평가|내역|기준|구분")


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+|\(주\)|㈜|주식회사", "", name or "").lower()


def is_plausible_entity(scope: str | None) -> bool:
    """백필이 붙인 소속 이름이 법인명처럼 보이는지. '장기카드대출 업무', '2022년 이사회 평가 결과' 같은 제목은 제외한다."""
    if not scope:
        return False
    name = scope.strip()
    if len(name) > 30 or _NOT_ENTITY.search(name):
        return False
    return bool(_ENTITY_SUFFIX.search(name)) or (" " not in name and len(name) <= 12)


def entity_scope_violations(text: str, cited: Iterable[CitedText], company_name: str) -> list[Violation]:
    """자회사(소속 법인) 표의 숫자를 쓰면서 그 법인명을 밝히지 않은 문장을 잡는다.

    우리금융지주 실측: 【 우리자산운용 】 표의 영업이익 22,133백만원을 지주사 전체 영업이익으로 썼다.
    숫자는 근거에 있어 숫자 검사는 통과하므로, 주체를 따로 검사한다.
    """
    own = _normalize_name(company_name)
    plain_text = _normalize_name(text)
    violations: list[Violation] = []
    numbers = {m.group(0) for m in _AMOUNT_TOKEN.finditer(text)} | {m.group(1) for m in _UNIT_NUMBER.finditer(text)}
    if not numbers:
        return []
    for row in cited:
        scope = row.scope
        if not is_plausible_entity(scope):
            continue
        scope_norm = _normalize_name(scope)
        if not scope_norm or scope_norm == own or scope_norm in own or own in scope_norm:
            continue  # 회사 자신의 표
        uses_row = any(_digits_present(number, row.content) for number in numbers)
        if uses_row and scope_norm not in plain_text:
            violations.append(Violation("segment_as_company", f"{scope} 표의 숫자를 쓰면서 소속 법인을 밝히지 않음"))
            break
    return violations


_SUBJECT_AFTER = r"\s*(?:의|은|는|이|가|에서|에서는)"


def company_as_segment_violations(
    text: str, cited: Iterable[CitedText], scopes: Iterable[str], company_name: str
) -> list[Violation]:
    """자회사 이름이 주어인 문장에 회사 전체 숫자를 쓴 경우를 잡는다(역방향).

    우리금융지주 실측: "우리은행의 2025년 영업이익은 3.7조원" — 3.7조원은 지주사 확정 지표다.
    자회사 X 가 주어(X의/X은/X는)인 문장의 금액·비율은 X 소속 표나 X 를 언급하는 근거에 있어야 한다.
    회사 자신의 이름이 같은 문장에 있으면(비교 문장) 검사하지 않는다.
    """
    own = _normalize_name(company_name)
    cited = list(cited)
    entities = [s for s in {s for s in scopes if s} if is_plausible_entity(s) and _normalize_name(s) not in (own, "") and _normalize_name(s) not in own]
    if not entities:
        return []
    violations: list[Violation] = []
    for sentence in _SENTENCE_SPLIT.split(text):
        norm_sentence = _normalize_name(sentence)
        if own and own in norm_sentence:
            continue
        subject = next(
            (e for e in entities if re.search(re.escape(e) + _SUBJECT_AFTER, sentence) or re.search(re.escape(e) + _SUBJECT_AFTER, norm_sentence)),
            None,
        )
        if subject is None:
            continue
        numbers = [m.group(0) for m in _AMOUNT_TOKEN.finditer(sentence)] + [m.group(1) for m in _UNIT_NUMBER.finditer(sentence)] + [m.group(0) for m in _RATIO_TOKEN.finditer(sentence)]
        if not numbers:
            continue
        subject_norm = _normalize_name(subject)
        for number in numbers:
            holders = [row for row in cited if _digits_present(number, row.content) or _ratio_present(number, [row])]
            if not holders:
                continue  # 숫자 검사가 따로 잡는다
            if not any(_normalize_name(row.scope or "") == subject_norm or subject_norm in _normalize_name(row.content) for row in holders):
                violations.append(
                    Violation(
                        "company_as_segment",
                        f"{subject} 주어 문장의 숫자 {number}는 {company_name} 전체 수치이고 {subject} 근거에 없음. "
                        f"{subject}의 수치는 '소속 법인: {subject}' 표에서만 가져오고, 없으면 {subject} 수치를 쓰지 않는다",
                    )
                )
                break
    return violations


_WRONG_UNIT_AFTER = re.compile(r"^\s*((?:천|백만|억|천만|십억|조)?\s*원)")


def _source_money_units(number: str, holders: Iterable[CitedText]) -> set[str]:
    """원문에서 이 숫자 바로 뒤에 붙은 금액 단위들(공백 제거). 표 행의 숫자는 보통 단위가 안 붙어 비어 있다."""
    units: set[str] = set()
    for row in holders:
        for variant in (number, number.replace(",", "")):
            for match in re.finditer(rf"(?<![\d,.]){re.escape(variant)}(?![\d,]|\.\d)", row.content):
                unit = _WRONG_UNIT_AFTER.match(row.content[match.end(): match.end() + _NEXT_TOKEN_WINDOW])
                if unit:
                    units.add(unit.group(1).replace(" ", ""))
    return units


def fix_unit_mismatches(text: str, cited: Iterable[CitedText]) -> str:
    """금액 표의 숫자 뒤에 붙은 잘못된 원화 단위를 표 단위로 바꿔 쓴다.

    우리자산운용 실측: 표 단위 백만원인 22,133 을 모델이 두 번 연속 '22,133억원' 으로 썼다. 표 단위를 코드가 알고
    있으므로 다시 묻지 않고 고친다. 표 단위가 하나로 정해질 때만 고치고, 숫자 자체는 바꾸지 않는다.
    """
    cited = list(cited)
    out = text
    for match in list(_AMOUNT_TOKEN.finditer(text))[::-1]:  # 뒤에서부터 바꿔야 앞 인덱스가 유지된다
        number = match.group(0)
        holders = [row for row in cited if _digits_present(number, row.content)]
        if not holders:
            continue
        # 원문에 숫자 뒤 단위가 붙어 있으면 그 단위로, 표 행의 숫자면 표 단위로 고친다.
        expected = _source_money_units(number, holders)
        if not expected and all(is_money_table(row) and _in_table_rows(number, row) for row in holders):
            expected = {row.unit.strip() for row in holders if row.unit and row.unit.strip() in _MONEY_UNITS}
        if len(expected) != 1:
            continue
        unit = next(iter(expected))
        after = out[match.end(): match.end() + _NEXT_TOKEN_WINDOW]
        wrong = _WRONG_UNIT_AFTER.match(after)
        if not wrong or _unit_follows(after, unit):
            continue
        out = out[: match.end()] + unit + out[match.end() + wrong.end(1):]
    return out


# --- 시장 통계 ------------------------------------------------------------------

_USD = re.compile(r"US\s*\$|\$\s*\d|달러")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?다요])\s+")


def market_stat_violations(text: str, company_name: str) -> list[Violation]:
    """회사가 주어인 문장에 달러 금액이 있으면 잡는다.

    국내 상장사의 자기 실적은 원화다. 달러 금액은 거의 항상 가트너·IDC 같은 시장 통계인데, SK하이닉스 실측에서
    'HBM 수요가 $1,356억을 기록' 처럼 시장 규모를 회사 실적처럼 썼다.
    """
    own = _normalize_name(company_name)
    if not own:
        return []
    violations: list[Violation] = []
    for sentence in _SENTENCE_SPLIT.split(text):
        if not _USD.search(sentence):
            continue
        if own in _normalize_name(sentence) or re.search(r"당사|회사는|회사의", sentence):
            if not re.search(r"시장|수요|출하|산업|규모|전망|가트너|IDC|옴디아|트렌드포스", sentence):
                violations.append(Violation("market_stat_as_company", f"회사 주어 문장에 달러 금액: '{sentence.strip()[:80]}'"))
    return violations


def _unit_follows(after: str, unit: str) -> bool:
    pattern = r"\s*".join(re.escape(ch) for ch in unit)
    return re.match(rf"^\s*{pattern}", after) is not None

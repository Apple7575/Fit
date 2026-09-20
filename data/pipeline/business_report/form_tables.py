"""DART 서식 표를 행 단위 레코드로 푼다 (docs/decisions/0003).

사업보고서 표 가운데 DART 가 서식을 정해 100개사에 같은 머리글로 나오는 표(직원 현황, 임원 현황,
계열회사, 타법인출자 등)를 골라 `행 이름 경로 × 열 이름 경로 → 값` 의 긴 레코드로 바꾼다.
청킹·임베딩과는 독립이다. 표 하나를 그대로 두고 이 모듈은 읽기만 한다.

핵심 규칙
- 머리글: THEAD 행 수(`header_rows`)를 우선 쓰고, 없으면 앞에서부터 "숫자가 하나도 없는 행"을 머리글로 본다.
  같은 이름이 옆으로 반복되면(colspan) 아래 행과 합쳐 `수주총액 > 금액` 처럼 경로를 만든다.
- 단위 줄: `(단위 : 백만원)` 만 있는 줄은 머리글이 아니라 단위다.
- 열 밀림: 서식이 정한 필수 머리글이 있어도 본문 행의 열 수가 머리글과 다르거나, 숫자여야 할 열에
  숫자가 절반도 없으면 `MISALIGNED` 로 표시한다. 값은 남기되 숫자 답에 쓰지 않는다.
- 값: 콤마·괄호 음수·△ 음수·% 를 읽는다. 읽히지 않으면 `value_text` 만 남기고 `TEXT` 로 표시한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from ..normalize.text import squash
from .doc import Document, Table

# --- 서식 정의 ---------------------------------------------------------------


@dataclass(frozen=True)
class FormSpec:
    code: str
    label: str
    section: re.Pattern[str]          # 절 제목 조건
    required: tuple[str, ...]         # 머리글에 반드시 있어야 하는 이름(공백 제거 후 부분 일치)
    numeric: tuple[str, ...] = ()     # 숫자여야 하는 머리글 이름(부분 일치). 열 밀림 판정에 쓴다.
    default_unit: str | None = None   # 단위 메타가 비었을 때
    patterns: tuple[tuple[str, str], ...] = ()  # (머리글 이름, 값 정규식). 값 절반 이상이 안 맞으면 열 밀림


_DATE = r"^\d{4}[.\-/]\d{1,2}([.\-/]\d{1,2})?$|^\d{4}년"
FORM_SPECS: tuple[FormSpec, ...] = (
    # DART 직원 등 현황: 성별·기간 구분별 직원 수, 평균근속연수, 급여. 단위는 표 밖 '(단위 : 백만원)' 에 있고 표본 5개사 모두 못 찾았다.
    FormSpec("EMPLOYEE_STATUS", "직원 현황", re.compile(r"임원\s*및\s*직원"), ("평균근속연수", "1인평균급여액"), ("연간급여총액", "1인평균급여액"), "백만원"),
    # DART 미등기임원 보수 현황: 구분(미등기임원) · 인원수 · 연간급여 총액 · 1인평균 급여액. 실측 값(덕산테코피아 10명 1,219)은 백만원 단위다.
    FormSpec("EXECUTIVE_PAY", "미등기임원 보수", re.compile(r"임원\s*및\s*직원"), ("인원수", "1인평균급여액"), ("인원수", "연간급여총액", "1인평균급여액"), "백만원"),
    FormSpec("EXECUTIVE_STATUS", "임원 현황", re.compile(r"임원\s*및\s*직원"), ("성명", "직위", "담당업무"), (), None, (("출생년월", r"^\d{4}[.\-/]\d{1,2}$|^\d{4}년"),)),
    FormSpec("AFFILIATE_LIST", "계열회사 현황", re.compile(r"계열회사"), ("기업명", "법인등록번호"), (), None, (("상장여부", r"^(상장|비상장|코스닥|코스피|코넥스)"),)),
    FormSpec("EQUITY_INVESTMENT", "타법인출자 현황", re.compile(r"타법인\s*출자"), ("법인명", "최초취득일자", "출자목적", "기말잔액"), ("최초취득금액", "기말잔액>수량", "기말잔액>지분율", "기말잔액>장부가액"), "백만원",
             (("상장여부", r"^(상장|비상장)"), ("최초취득일자", _DATE))),
    FormSpec("RND_EXPENSE", "연구개발비", re.compile(r"연구개발"), ("연구개발비",), (), "백만원"),
    FormSpec("ORDER_BACKLOG", "수주상황", re.compile(r"매출\s*및\s*수주"), ("품목", "수주총액", "수주잔고"), ("수주총액>금액", "수주잔고>금액"), "백만원"),
    FormSpec("SALES_BY_PRODUCT", "매출실적", re.compile(r"매출\s*및\s*수주|주요\s*제품"), ("매출유형", "품목"), (), "백만원"),
)

_UNIT_ONLY = re.compile(r"^\(?\s*단\s*위\s*[:：]?\s*[^)]*\)?$")
_UNIT_VALUE = re.compile(r"단\s*위\s*[:：]?\s*([가-힣A-Za-z$₩,%\s]+?)\s*\)?$")
_HAS_DIGIT = re.compile(r"\d")
_NUMBER = re.compile(r"^\(?\s*[-−△▲]?\s*\(?\s*\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*\)?\s*%?\s*\)?$")
_PERIOD = re.compile(r"제\s*(\d{1,3})\s*기|((?:19|20)\d{2})\s*년?")


@dataclass
class FormRow:
    form_code: str
    table_index: int
    row_no: int
    row_labels: tuple[str, ...]
    column_key: str
    value_text: str
    value_num: float | None
    unit: str | None
    fiscal_year: int | None
    parse_status: str          # NUMBER | TEXT | MISALIGNED
    entity_scope: str | None
    section_title: str


@dataclass
class FormTable:
    form_code: str
    table_index: int
    section_title: str
    header: tuple[str, ...]
    header_rows: int
    unit: str | None
    entity_scope: str | None
    misaligned_reason: str | None
    rows: list[FormRow] = field(default_factory=list)

    @property
    def status(self) -> str:
        return "MISALIGNED" if self.misaligned_reason else "OK"


# --- 머리글 ------------------------------------------------------------------


def _norm(cell: str) -> str:
    return re.sub(r"\s+", "", squash(cell))


def _is_unit_line(row: list[str]) -> bool:
    cells = [_norm(c) for c in row if _norm(c)]
    return bool(cells) and all(_UNIT_ONLY.match(c) for c in cells)


def _unit_from_row(row: list[str]) -> str | None:
    for cell in row:
        m = _UNIT_VALUE.search(squash(cell))
        if m:
            return m.group(1).strip()
    return None


def _looks_like_header_row(row: list[str]) -> bool:
    cells = [_norm(c) for c in row if _norm(c)]
    if not cells:
        return False
    # 머리글에도 "2023년(제39기)" 처럼 숫자가 있으므로, 순수 숫자 셀이 없는지로 본다.
    return not any(_NUMBER.match(c) for c in cells)


def split_header(table: Table) -> tuple[list[list[str]], list[list[str]], str | None]:
    """(머리글 행들, 본문 행들, 표 안에서 찾은 단위). 단위만 있는 줄은 머리글에서 뺀다."""
    rows = [list(r) for r in table.m]
    unit: str | None = None
    while rows and _is_unit_line(rows[0]):
        unit = unit or _unit_from_row(rows[0])
        rows.pop(0)
    if not rows:
        return [], [], unit
    count = table.header_rows
    if count <= 0:
        count = 0
        for row in rows[:3]:
            if _looks_like_header_row(row):
                count += 1
            else:
                break
        count = max(count, 1) if _looks_like_header_row(rows[0]) else 0
    # 첫 본문 행이 머리글과 똑같이 반복되는 경우(둘째 머리글 줄이 TBODY 에 있음)
    while count < len(rows) and count < 3 and _looks_like_header_row(rows[count]) and _repeats_header(rows[:count], rows[count]):
        count += 1
    return rows[:count], rows[count:], unit


def _repeats_header(header: list[list[str]], row: list[str]) -> bool:
    if not header:
        return False
    top = [_norm(c) for c in header[0]]
    cur = [_norm(c) for c in row]
    if len(cur) != len(top):
        return False
    same = sum(1 for a, b in zip(top, cur) if a == b)
    return same >= max(1, len(top) // 3)


def header_paths(header: list[list[str]]) -> tuple[str, ...]:
    """머리글 여러 줄을 열별 경로로 합친다. 같은 이름이 위·아래로 반복되면 한 번만 쓴다."""
    if not header:
        return ()
    width = max(len(r) for r in header)
    paths: list[str] = []
    for col in range(width):
        parts: list[str] = []
        for row in header:
            cell = _norm(row[col]) if col < len(row) else ""
            if cell and (not parts or parts[-1] != cell):
                parts.append(cell)
        paths.append(">".join(parts))
    return tuple(paths)


# --- 값 ----------------------------------------------------------------------


def parse_number(text: str) -> float | None:
    raw = _norm(text)
    if not raw or raw in {"-", "—", "–", "－"}:
        return None
    if not _NUMBER.match(raw):
        return None
    negative = raw.startswith(("(", "-", "−", "△", "▲")) or raw.endswith(")")
    digits = re.sub(r"[^\d.]", "", raw)
    if not digits or digits == ".":
        return None
    value = float(digits)
    return -value if negative and value != 0 else value


def period_year(column_key: str, report_year: int, latest_period: int | None) -> int | None:
    """'제51기' 또는 '2023년(제39기)' 에서 연도. 기수만 있으면 가장 큰 기수를 보고서 연도로 두고 거꾸로 센다."""
    m = _PERIOD.search(column_key)
    if not m:
        return None
    if m.group(2):
        return int(m.group(2))
    if latest_period is None:
        return None
    return report_year - (latest_period - int(m.group(1)))


def _latest_period(paths: Iterable[str]) -> int | None:
    numbers = [int(m.group(1)) for p in paths for m in _PERIOD.finditer(p) if m.group(1)]
    return max(numbers) if numbers else None


# --- 표 → 레코드 -----------------------------------------------------------------


def detect_form(table: Table, paths: tuple[str, ...]) -> FormSpec | None:
    joined = "|".join(paths)
    for spec in FORM_SPECS:
        if not spec.section.search(table.title or ""):
            continue
        if all(name in joined for name in spec.required):
            return spec
    return None


def _label_columns(paths: tuple[str, ...], body: list[list[str]]) -> int:
    """앞에서부터 몇 열이 행 이름인가. 본문에서 숫자가 거의 없는 선두 열들."""
    count = 0
    for col in range(len(paths)):
        cells = [_norm(r[col]) for r in body if col < len(r) and _norm(r[col])]
        if not cells:
            break
        numeric = sum(1 for c in cells if parse_number(c) is not None)
        if numeric > len(cells) * 0.3:
            break
        count += 1
    return max(count, 1) if paths else 0


def form_tables(document: Document, *, report_year: int) -> list[FormTable]:
    """문서의 표 중 서식에 맞는 것만 레코드로 푼다. 표 좌표(`table.idx`)는 청킹과 같다."""
    result: list[FormTable] = []
    for table in document.tables:
        if table.excluded_reason or not table.m:
            continue
        header, body, unit_in_table = split_header(table)
        paths = header_paths(header)
        spec = detect_form(table, paths)
        if spec is None:
            continue
        if not body:
            continue  # 머리글만 있거나 각주만 있는 표. 서식 표가 아니다.
        doc_unit, _, _ = document.unit(table)
        unit = unit_in_table or doc_unit or spec.default_unit
        reason = _misaligned_reason(spec, paths, body)
        form = FormTable(spec.code, table.idx, table.title, paths, len(header), unit, table.entity_scope, reason)
        labels_n = _label_columns(paths, body)
        latest = _latest_period(paths)
        for row_no, row in enumerate(body):
            labels = tuple(squash(c) for c in row[:labels_n])
            for col in range(labels_n, min(len(paths), len(row))):
                text = squash(row[col])
                if not text:
                    continue
                number = parse_number(text)
                status = "MISALIGNED" if reason else ("NUMBER" if number is not None else "TEXT")
                form.rows.append(FormRow(
                    spec.code, table.idx, row_no, labels, paths[col], text, number,
                    unit if number is not None else None, period_year(paths[col], report_year, latest),
                    status, table.entity_scope, table.title,
                ))
        result.append(form)
    return result


def _misaligned_reason(spec: FormSpec, paths: tuple[str, ...], body: list[list[str]]) -> str | None:
    widths = [len(r) for r in body]
    off = sum(1 for w in widths if w != len(paths))
    if off > len(body) * 0.2:
        return f"width_mismatch:{off}/{len(body)}"
    for name, pattern in spec.patterns:
        regex = re.compile(pattern)
        for col in [i for i, p in enumerate(paths) if name in p]:
            cells = [_norm(r[col]) for r in body if col < len(r) and _norm(r[col]) and _norm(r[col]) not in {"-", "—"}]
            if len(cells) >= 2 and sum(1 for c in cells if regex.search(c)) < len(cells) * 0.5:
                return f"pattern_mismatch:{paths[col]}"
    for name in spec.numeric:
        cols = [i for i, p in enumerate(paths) if name in p]
        for col in cols:
            cells = [_norm(r[col]) for r in body if col < len(r) and _norm(r[col]) and _norm(r[col]) not in {"-", "—"}]
            if len(cells) >= 3 and sum(1 for c in cells if parse_number(c) is not None) < len(cells) * 0.5:
                return f"non_numeric_column:{paths[col]}"
    return None

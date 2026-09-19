"""정형화된 서식 표 행(company_table_row)을 서술 근거로 바꾼다 (docs/decisions/0003 3단계).

리포트 서술은 지금까지 사업보고서 표를 텍스트 청크 그대로 모델에 보여 주고 모델이 숫자를 읽어 옮겼다.
부문 이익을 지주사 전체로 쓰는 식의 오류가 여기서 났다. 이제 서식 표는 `company_table_row` 의
LINKED 행(값이 원문과 대조됐고 인용할 청크가 있는 행)만 읽어, 행 이름·연도·값·단위·소속 법인이
분리된 짧은 블록으로 모델에 넘긴다. 같은 표의 원문 청크는 근거에서 뺀다. 모델은 표를 읽지 않고
넘겨받은 값으로 문장만 쓴다. PENDING_CHUNK 행은 재청킹 전이라 쓰지 않는다(검수 판정 2026-09-19).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Protocol, Sequence

from .contracts import Citation
from .evidence import SOURCE_TYPE

# 서술 계획 → 넣을 서식. 매출실적·수주는 사업 섹션의 숫자 근거다.
PLAN_FORMS: dict[str, tuple[str, ...]] = {
    "BUSINESS_CORE": ("SALES_BY_PRODUCT",),
    "BUSINESS_GROWTH": ("SALES_BY_PRODUCT", "ORDER_BACKLOG"),
}
FORM_LABELS = {
    "SALES_BY_PRODUCT": "매출실적·주요 제품 매출",
    "ORDER_BACKLOG": "수주상황",
    "EMPLOYEE_STATUS": "직원 현황",
    "EXECUTIVE_PAY": "미등기임원 보수",
    "EXECUTIVE_STATUS": "임원 현황",
    "AFFILIATE_LIST": "계열회사 현황",
    "EQUITY_INVESTMENT": "타법인출자 현황",
}
MAX_ROWS_PER_TABLE = 40
MAX_CHARS_PER_TABLE = 1_400


@dataclass(frozen=True)
class TableFactRow:
    rcept_no: str
    table_index: int
    form_code: str
    section_title: str
    entity_scope: str | None
    unit: str | None
    matrix_row: int
    row_labels: tuple[str, ...]
    column_key: str
    fiscal_year: int | None
    value_num: float | None
    value_text: str
    parse_status: str
    evidence_id: str | None


@dataclass(frozen=True)
class FactBlock:
    evidence_id: str          # 근거 ID: facts:<form>:<rcept>:<table>
    form_code: str
    rcept_no: str
    table_index: int
    title: str
    content: str
    unit: str | None
    entity_scope: str | None
    citation: Citation


class TableFactsRepository(Protocol):
    def rows(self, corp_code: str, rcept_no: str) -> list[TableFactRow]: ...


_ROWS_SQL = """
SELECT rcept_no, table_index, form_code, section_title, entity_scope, unit, matrix_row, row_labels, column_key,
       fiscal_year, value_num, value_text, parse_status, evidence_id
FROM company_table_row
WHERE corp_code = %s AND rcept_no = %s AND evidence_status = 'LINKED' AND parse_status <> 'MISALIGNED'
ORDER BY form_code, table_index, matrix_row, col_no
"""


class PostgresTableFactsRepository:
    def __init__(self, connect: Callable[[], Any]) -> None:
        self._connect = connect

    def rows(self, corp_code: str, rcept_no: str) -> list[TableFactRow]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(_ROWS_SQL, (corp_code, rcept_no))
            return [
                TableFactRow(r[0], int(r[1]), r[2], r[3] or "", r[4], r[5], int(r[6]), tuple(r[7] or ()), r[8],
                             r[9], float(r[10]) if r[10] is not None else None, r[11] or "", r[12], r[13])
                for r in cursor.fetchall()
            ]


def _format(row: TableFactRow) -> str:
    if row.value_num is None:
        return row.value_text
    value = f"{row.value_num:,.2f}".rstrip("0").rstrip(".")
    if "%" in row.value_text or "비율" in row.column_key or "지분율" in row.column_key:
        return f"{value}%"
    return f"{value}{row.unit or ''}"


def render_blocks(rows: Sequence[TableFactRow], form_codes: Sequence[str]) -> list[FactBlock]:
    """표 하나 → 블록 하나. 한 줄은 `행 이름 | 열(연도): 값단위`. 숫자 행을 우선하고 길이를 제한한다."""
    by_table: dict[tuple[str, str, int], list[TableFactRow]] = defaultdict(list)
    for row in rows:
        if row.form_code in form_codes and row.evidence_id:
            by_table[(row.form_code, row.rcept_no, row.table_index)].append(row)
    blocks: list[FactBlock] = []
    for (form_code, rcept_no, table_index), table_rows in sorted(by_table.items()):
        first = table_rows[0]
        lines: list[str] = []
        by_line: dict[tuple[int, tuple[str, ...]], list[str]] = defaultdict(list)
        for row in table_rows:
            if row.value_text in ("", "-"):
                continue
            # '2023년(제18기)' 처럼 열 이름에 연도가 이미 있으면 덧붙이지 않는다.
            year = f"({row.fiscal_year}년)" if row.fiscal_year and str(row.fiscal_year) not in row.column_key else ""
            by_line[(row.matrix_row, row.row_labels)].append(f"{row.column_key}{year}: {_format(row)}")
        for (_, labels), values in sorted(by_line.items()):
            if not values:
                continue
            lines.append(f"{' > '.join(labels) or '(행 이름 없음)'} | " + " · ".join(values))
            if len(lines) >= MAX_ROWS_PER_TABLE:
                lines.append("(이하 행 생략)")
                break
        if not lines:
            continue
        head = [f"표 단위: {first.unit}" if first.unit else "표 단위: (표기 없음)"]
        if first.entity_scope:
            head.append(f"소속 법인: {first.entity_scope} (이 표의 숫자는 {first.entity_scope} 의 것이다)")
        head.append("정형화된 값이다. 아래 숫자만 그대로 쓰고 계산하지 않는다.")
        content = "\n".join(head + lines)
        if len(content) > MAX_CHARS_PER_TABLE:
            content = content[:MAX_CHARS_PER_TABLE].rsplit("\n", 1)[0] + "\n(이하 행 생략)"
        evidence_id = f"facts:{form_code}:{rcept_no}:{table_index}"
        blocks.append(FactBlock(
            evidence_id, form_code, rcept_no, table_index,
            title=f"정형 표 · {FORM_LABELS.get(form_code, form_code)} · {first.section_title}".strip(" ·"),
            content=content, unit=first.unit, entity_scope=first.entity_scope,
            citation=Citation(source_type=SOURCE_TYPE, source_id=first.evidence_id or evidence_id, rcept_no=rcept_no, excerpt=content[:1_000]),
        ))
    return blocks


def covered_tables(blocks: Sequence[FactBlock]) -> set[tuple[str, int]]:
    return {(b.rcept_no, b.table_index) for b in blocks}

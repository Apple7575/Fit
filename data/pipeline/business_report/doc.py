"""사업보고서 XML 한 건을 본문과 표의 원문 계보로 읽는다."""
from __future__ import annotations

import re
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from ..normalize.rnd import load_xml, parse_xml_bytes, matrix
from ..normalize.text import squash
from ..patterns import Patterns, patterns as default_patterns


TEXT_TAGS = ("P", "SPAN", "TU")
_UNIT_SCOPE = re.compile(r"단위\s*[)\]]?\s*[::]?\s*([^)\]|]{0,20})")


def _is_in_table(element) -> bool:
    parent = element.getparent()
    while parent is not None:
        if isinstance(parent.tag, str) and parent.tag.upper() == "TABLE":
            return True
        parent = parent.getparent()
    return False


def unit_from_blob(blob: str, units) -> tuple[str, int] | None:
    for match in _UNIT_SCOPE.finditer(blob):
        for name, multiplier in units:
            if name in match.group(1):
                return name, multiplier
    return None


@dataclass
class Table:
    idx: int
    title: str
    caption: str
    m: list[list[str]]
    excluded_reason: str | None = None

    @property
    def rows(self) -> int:
        return len(self.m)

    def head(self, n: int = 3) -> str:
        return " ".join(" ".join(row) for row in self.m[:n])


@dataclass(frozen=True)
class ParagraphEntry:
    index: int
    text: str


@dataclass
class Section:
    title: str
    paragraphs: list[str] = field(default_factory=list)
    paragraph_entries: list[ParagraphEntry] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)

    def text(self, limit: int | None = None) -> str:
        value = "\n".join(self.paragraphs)
        return value[:limit] if limit else value


def _normalized_span(value: str | None) -> int | None:
    try:
        numeric = float(value or "1")
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(numeric):
        return None
    return max(1, int(numeric))


def _table_shape(table, cell_tags: set[str], *, max_table_cells: int) -> tuple[int, int] | None:
    """`matrix`와 같은 span 규칙으로 행과 열의 곱을 계산하되 격자는 만들지 않는다."""
    pending: list[tuple[int, int, int]] = []
    row_count = 0
    width = 0
    for row in table.iter("TR"):
        row_count += 1
        column = 0
        row_width = max((end for _, end, _ in pending), default=0)
        if row_count * max(width, row_width) > max_table_cells:
            return row_count, max(width, row_width)
        for cell in row:
            tag = cell.tag.upper() if isinstance(cell.tag, str) else ""
            if tag not in cell_tags:
                continue
            colspan = _normalized_span(cell.get("COLSPAN") or cell.get("colspan"))
            rowspan = _normalized_span(cell.get("ROWSPAN") or cell.get("rowspan"))
            if colspan is None or rowspan is None:
                return None
            column = _next_free_column(column, pending)
            end = column + colspan
            row_width = max(row_width, end)
            width = max(width, row_width)
            if row_count * width > max_table_cells:
                return row_count, width
            if rowspan > 1:
                pending = _overlay_pending(pending, column, end, rowspan - 1)
            column = end
        pending = _decrement_pending(pending)
    return row_count, width


def _next_free_column(column: int, pending: list[tuple[int, int, int]]) -> int:
    for start, end, _ in pending:
        if column < start:
            break
        if column < end:
            return end
    return column


def _overlay_pending(
    pending: list[tuple[int, int, int]], start: int, end: int, remaining: int,
) -> list[tuple[int, int, int]]:
    """행 안에서 새 rowspan이 기존 pending 열을 덮어쓰는 matrix 규칙을 구간으로 재현한다."""
    intervals: list[tuple[int, int, int]] = []
    for current_start, current_end, current_remaining in pending:
        if current_end <= start or end <= current_start:
            intervals.append((current_start, current_end, current_remaining))
            continue
        if current_start < start:
            intervals.append((current_start, start, current_remaining))
        if end < current_end:
            intervals.append((end, current_end, current_remaining))
    intervals.append((start, end, remaining))
    intervals.sort()
    merged: list[tuple[int, int, int]] = []
    for interval in intervals:
        if merged and merged[-1][1] == interval[0] and merged[-1][2] == interval[2]:
            previous = merged.pop()
            merged.append((previous[0], interval[1], previous[2]))
        else:
            merged.append(interval)
    return merged


def _decrement_pending(pending: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    return [
        (start, end, remaining - 1)
        for start, end, remaining in pending
        if remaining - 1 > 0
    ]


class Document:
    """사업보고서 하나를 한 번 순회해 섹션, 문단, 표를 만든다."""

    def __init__(
        self, source: Path | str | bytes | bytearray, p: Patterns | None = None, *, rcept_no: str | None = None,
        max_table_cells: int = 200_000,
    ):
        self.p = p or default_patterns()
        self.max_table_cells = max_table_cells
        self._excluded_table_counts: Counter[str] = Counter()
        if isinstance(source, (bytes, bytearray)):
            self.path = None
            self.rcept_no = rcept_no or ""
            root, self.encoding = parse_xml_bytes(bytes(source), f"document_{self.rcept_no}.xml")
        else:
            self.path = Path(source)
            self.rcept_no = rcept_no or self.path.stem.replace("document_", "")
            root, self.encoding = load_xml(self.path)
        self.sections: list[Section] = []
        self.tables: list[Table] = []
        self._walk(root)

    @classmethod
    def from_bytes(
        cls, payload: bytes | bytearray, *, rcept_no: str, p: Patterns | None = None,
        max_table_cells: int = 200_000,
    ) -> "Document":
        return cls(payload, p, rcept_no=rcept_no, max_table_cells=max_table_cells)

    def _walk(self, root) -> None:
        current = Section(title="")
        self.sections.append(current)
        recent: list[str] = []
        paragraph_index = 0
        table_index = 0
        for element in root.iter():
            tag = element.tag.upper() if isinstance(element.tag, str) else ""
            if tag == "TITLE":
                current = Section(title=squash("".join(element.itertext())))
                self.sections.append(current)
                recent = []
                paragraph_index = 0
            elif tag in TEXT_TAGS:
                if _is_in_table(element):
                    continue
                text = squash("".join(element.itertext()))
                current.paragraph_entries.append(ParagraphEntry(paragraph_index, text))
                paragraph_index += 1
                if text:
                    current.paragraphs.append(text)
                    recent = (recent + [text])[-4:]
            elif tag == "TABLE":
                excluded_reason = None
                shape = _table_shape(element, self.p.rnd.cell_tags, max_table_cells=self.max_table_cells)
                if shape is None:
                    excluded_reason = "table_invalid_span"
                    self._excluded_table_counts[excluded_reason] += 1
                    table_matrix = []
                elif shape[0] * shape[1] > self.max_table_cells:
                    excluded_reason = "table_too_large"
                    self._excluded_table_counts[excluded_reason] += 1
                    table_matrix: list[list[str]] = []
                else:
                    table_matrix = matrix(element, self.p)
                table = Table(
                    idx=table_index,
                    title=current.title,
                    caption=" | ".join(recent[-3:]),
                    m=table_matrix,
                    excluded_reason=excluded_reason,
                )
                self.tables.append(table)
                current.tables.append(table)
                table_index += 1
                recent = []

    @property
    def excluded_table_counts(self) -> dict[str, int]:
        return dict(self._excluded_table_counts)

    def sections_matching(self, rx) -> list[Section]:
        return [section for section in self.sections if section.title and rx.search(section.title)]

    def tables_matching(self, rx, *, in_title=None) -> list[Table]:
        result = []
        for table in self.tables:
            if in_title is not None and not in_title.search(table.title):
                continue
            if rx.search(table.title) or rx.search(table.caption) or rx.search(table.head()):
                result.append(table)
        return result

    def unit(self, table: Table) -> tuple[str | None, int | None, str | None]:
        rules = self.p.rnd
        for index in range(table.idx, max(-1, table.idx - rules.unit_lookback_tables - 1), -1):
            candidate = self.tables[index]
            found = unit_from_blob(candidate.caption + " " + candidate.head(3), rules.units)
            if found:
                name, multiplier = found
                return name, multiplier, "자기표" if index == table.idx else f"직전표-{table.idx - index}"
        return None, None, None

"""사업보고서 XML 한 건을 본문과 표의 원문 계보로 읽는다."""
from __future__ import annotations

import re
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


def _positive_span(value: str | None) -> int:
    try:
        return max(1, int(float(value or "1")))
    except (ValueError, OverflowError):
        return 1


def _estimated_cells(table) -> int:
    total = 0
    for row in table.iter():
        if not isinstance(row.tag, str) or row.tag.upper() != "TR":
            continue
        for cell in row:
            if isinstance(cell.tag, str) and cell.tag.upper() in {"TD", "TH"}:
                total += _positive_span(cell.get("ROWSPAN") or cell.get("rowspan")) * _positive_span(
                    cell.get("COLSPAN") or cell.get("colspan")
                )
    return total


class Document:
    """사업보고서 하나를 한 번 순회해 섹션, 문단, 표를 만든다."""

    def __init__(
        self, path: Path | str, p: Patterns | None = None, max_table_cells: int = 200_000
    ):
        self.path = Path(path)
        self.rcept_no = self.path.stem.replace("document_", "")
        self.p = p or default_patterns()
        self.max_table_cells = max_table_cells
        self._excluded_table_counts: Counter[str] = Counter()
        root, self.encoding = load_xml(self.path)
        self.sections: list[Section] = []
        self.tables: list[Table] = []
        self._walk(root)

    @classmethod
    def from_bytes(
        cls, payload: bytes, *, rcept_no: str, p: Patterns | None = None,
        max_table_cells: int = 200_000,
    ) -> "Document":
        instance = cls.__new__(cls)
        instance.path = None
        instance.rcept_no = rcept_no
        instance.p = p or default_patterns()
        instance.max_table_cells = max_table_cells
        instance._excluded_table_counts = Counter()
        root, instance.encoding = parse_xml_bytes(payload, f"document_{rcept_no}.xml")
        instance.sections = []
        instance.tables = []
        instance._walk(root)
        return instance

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
                if _estimated_cells(element) > self.max_table_cells:
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

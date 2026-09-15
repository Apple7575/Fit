from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import re

from lxml import etree

from pipeline.business_report.doc import Document
from pipeline.normalize.text import squash
from pipeline.rag_corpus.models import EvidenceRecord
from pipeline.rag_corpus.transform import content_hash, stable_evidence_id

from .dart_archive import DartArchive, DartDocumentRef
from .models import EvidenceBatch


_TOC_TITLE = re.compile(r"^(?:목\s*차|contents?)$", re.IGNORECASE)
_CERTIFICATION_TITLE = re.compile(r"대표이사.*확인|전자\s*서명|확인서")
_BOILERPLATE_TEXT = re.compile(r"^(?:\d+\s*)+$|^[-_=·.\s]+$")


@dataclass(frozen=True)
class _TableChunk:
    content: str
    row_start: int
    row_end: int
    row_part_index: int | None = None
    row_part_count: int | None = None


class BusinessReportSource:
    def __init__(self, archive: DartArchive, *, years: set[int] | None = None):
        self.archive = archive
        self.years = years

    def records(self, corp_code: str) -> list[EvidenceRecord]:
        return business_report_batch(self.archive, corp_code, years=self.years).records

    def inventory(self) -> dict[str, object]:
        inventory = self.archive.inventory()
        if self.years is None:
            return inventory
        documents = self.archive.documents(years=self.years)
        return {
            **inventory, "documents": len(documents),
            "companies": len({document.corp_code for document in documents}),
            "years": sorted(self.years), "uncompressed_xml_bytes": sum(document.size for document in documents),
        }


def business_report_records(
    archive: DartArchive, corp_code: str, *, years: set[int] | None = None, max_chars: int = 1500,
) -> list[EvidenceRecord]:
    return business_report_batch(archive, corp_code, years=years, max_chars=max_chars).records


def business_report_batch(
    archive: DartArchive, corp_code: str, *, years: set[int] | None = None, max_chars: int = 1500,
) -> EvidenceBatch:
    if max_chars < 200:
        raise ValueError("max_chars는 200 이상이어야 합니다")
    records: list[EvidenceRecord] = []
    inputs: Counter[str] = Counter()
    excluded: Counter[str] = Counter()
    failures: list[dict[str, str]] = []
    for ref in archive.documents(corp_code, years=years):
        inputs["documents"] += 1
        try:
            document = Document.from_bytes(archive.read(ref), rcept_no=ref.rcept_no)
            batch = _document_records(document, ref, max_chars=max_chars)
        except Exception as error:
            if not _is_xml_payload_error(error):
                raise
            failures.append({
                "corp_code": ref.corp_code, "rcept_no": ref.rcept_no, "document_file": ref.entry_name,
                "reason": "xml_parse_error", "exception_type": type(error).__name__, "message": str(error),
            })
            continue
        records.extend(batch.records)
        inputs.update(batch.input_counts)
        excluded.update(batch.excluded_counts)
    return EvidenceBatch(
        records=sorted(records, key=lambda record: (record.source_identity, record.evidence_id)),
        input_counts=dict(sorted(inputs.items())), excluded_counts=dict(sorted(excluded.items())),
        failures=tuple(failures),
    )


def _document_records(document: Document, ref: DartDocumentRef, *, max_chars: int) -> EvidenceBatch:
    published_at = _published_at(ref.rcept_dt)
    records: list[EvidenceRecord] = []
    inputs: Counter[str] = Counter({
        "sections": len(document.sections),
        "paragraphs": sum(len(section.paragraph_entries) for section in document.sections),
        "tables": len(document.tables),
    })
    excluded: Counter[str] = Counter(document.excluded_table_counts)
    seen_paragraphs: set[str] = set()
    for section_index, section in enumerate(document.sections):
        title = squash(section.title)
        skip_reason = _excluded_section_reason(title)
        if skip_reason:
            excluded[skip_reason] += 1
            continue

        paragraphs: list[tuple[int, str]] = []
        for entry in section.paragraph_entries:
            if not entry.text:
                excluded["blank_content"] += 1
            elif _BOILERPLATE_TEXT.fullmatch(entry.text):
                excluded["boilerplate_text"] += 1
            elif entry.text in seen_paragraphs:
                excluded["duplicate_content"] += 1
            else:
                seen_paragraphs.add(entry.text)
                paragraphs.append((entry.index, entry.text))
        for chunk_index, chunk in enumerate(_text_chunks(paragraphs, max_chars=max_chars)):
            content, paragraph_start, paragraph_end = chunk
            identity = f"dart_business_report:{ref.corp_code}:{ref.rcept_no}:{section_index}:text:{chunk_index}"
            metadata = _metadata(
                document, ref, section.title, section_index,
                content_type="TEXT", chunk_index=chunk_index,
                paragraph_start=paragraph_start, paragraph_end=paragraph_end,
            )
            records.append(_record(ref, published_at, section.title, identity, content, metadata))

        for table in section.tables:
            if table.excluded_reason:
                continue
            unit, _, _ = document.unit(table)
            for chunk in _table_chunks(table.caption, table.m, max_chars=max_chars):
                identity = (
                    f"dart_business_report:{ref.corp_code}:{ref.rcept_no}:{section_index}:"
                    f"table:{table.idx}:{chunk.row_start}:{chunk.row_end}"
                )
                metadata = _metadata(
                    document, ref, section.title, section_index, content_type="TABLE",
                    table_index=table.idx, row_start=chunk.row_start, row_end=chunk.row_end, unit=unit,
                )
                if chunk.row_part_index is not None:
                    identity += f":part:{chunk.row_part_index}"
                    metadata["row_part_index"] = chunk.row_part_index
                    metadata["row_part_count"] = chunk.row_part_count
                records.append(_record(ref, published_at, section.title, identity, chunk.content, metadata))
    return EvidenceBatch(records, dict(sorted(inputs.items())), dict(sorted(excluded.items())))


def _metadata(
    document: Document, ref: DartDocumentRef, section_title: str, section_index: int, *, content_type: str,
    **coordinates: object,
) -> dict[str, object]:
    return {
        "parent_id": f"dart-report:{ref.corp_code}:{ref.rcept_no}:{section_index}",
        "rcept_no": ref.rcept_no, "rcept_dt": ref.rcept_dt, "document_file": ref.entry_name,
        "report_name": ref.report_name, "section_title": section_title, "section_index": section_index,
        "section_path": str(section_index), "content_type": content_type,
        "chunk_schema_version": 2, "encoding": document.encoding, **coordinates,
    }


def _published_at(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y%m%d")
    except ValueError as error:
        raise ValueError(f"사업보고서 공개일이 잘못되었습니다: {value}") from error
    return parsed.replace(tzinfo=timezone.utc)


def _excluded_section_reason(title: str) -> str | None:
    if _TOC_TITLE.fullmatch(title):
        return "table_of_contents"
    if _CERTIFICATION_TITLE.search(title):
        return "certification_title"
    return None


def _text_chunks(paragraphs: list[tuple[int, str]], *, max_chars: int) -> list[tuple[str, int, int]]:
    chunks: list[tuple[str, int, int]] = []
    current = ""
    start = 0
    end = 0
    for index, paragraph in paragraphs:
        for offset in range(0, len(paragraph), max_chars):
            piece = paragraph[offset:offset + max_chars]
            candidate = piece if not current else current + "\n" + piece
            if current and len(candidate) > max_chars:
                chunks.append((current, start, end))
                current, start = piece, index
            elif not current:
                current, start = piece, index
            else:
                current = candidate
            end = index
    if current:
        chunks.append((current, start, end))
    return chunks


def _table_chunks(caption: str, matrix: list[list[str]], *, max_chars: int) -> list[_TableChunk]:
    indexed = [(index, [squash(cell) for cell in row]) for index, row in enumerate(matrix) if any(squash(cell) for cell in row)]
    if not indexed:
        return []
    header_index, header = indexed[0]
    prefix = _table_prefix(squash(caption), " | ".join(header), max_chars)
    if len(indexed) == 1:
        return [_TableChunk(prefix, header_index, header_index)]
    chunks: list[_TableChunk] = []
    current: list[tuple[int, str]] = []
    for row_index, cells in indexed[1:]:
        row = " | ".join(cells)
        candidate = prefix + "\n" + "\n".join(value for _, value in current + [(row_index, row)])
        if current and len(candidate) > max_chars:
            chunks.append(_TableChunk(prefix + "\n" + "\n".join(value for _, value in current), header_index, current[-1][0]))
            current = []
        if len(prefix) + 1 + len(row) > max_chars:
            chunks.extend(_split_table_row(prefix, header_index, row_index, cells, max_chars=max_chars))
        else:
            current.append((row_index, row))
    if current:
        chunks.append(_TableChunk(prefix + "\n" + "\n".join(value for _, value in current), header_index, current[-1][0]))
    return chunks


def _table_prefix(caption: str, header: str, max_chars: int) -> str:
    prefix = f"표 캡션: {caption}\n표 머리글: {header}"
    if len(prefix) <= max_chars - 2:
        return prefix
    labels = "표 캡션: \n표 머리글: "
    available = max(2, max_chars - 2 - len(labels))
    caption_limit = available // 2
    return f"표 캡션: {caption[:caption_limit]}\n표 머리글: {header[:available - caption_limit]}"


def _split_table_row(prefix: str, row_start: int, row_end: int, cells: list[str], *, max_chars: int) -> list[_TableChunk]:
    parts = _cell_parts(cells, max(1, max_chars - len(prefix) - 1))
    return [
        _TableChunk(f"{prefix}\n{part}", row_start, row_end, index, len(parts))
        for index, part in enumerate(parts)
    ]


def _cell_parts(cells: list[str], max_chars: int) -> list[str]:
    parts: list[str] = []
    current = ""
    for cell in cells:
        if len(cell) > max_chars:
            if current:
                parts.append(current)
                current = ""
            parts.extend(cell[offset:offset + max_chars] for offset in range(0, len(cell), max_chars))
            continue
        candidate = cell if not current else f"{current} | {cell}"
        if current and len(candidate) > max_chars:
            parts.append(current)
            current = cell
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


def _record(
    ref: DartDocumentRef, published_at: datetime, section_title: str, identity: str,
    content: str, metadata: dict[str, object],
) -> EvidenceRecord:
    title = f"{ref.corp_name} {ref.year}년 사업보고서 · {section_title}"
    source_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={ref.rcept_no}"
    payload = {
        "title": title, "content": content, "reference_period": str(ref.year),
        "source_url": source_url, "quality": "PRIMARY", "metadata": metadata,
    }
    return EvidenceRecord(
        evidence_id=stable_evidence_id(identity), corp_code=ref.corp_code,
        source_type="DART_BUSINESS_REPORT", source_identity=identity, title=title,
        content=content, reference_period=str(ref.year), published_at=published_at,
        source_url=source_url, quality="PRIMARY", metadata=metadata,
        content_hash=content_hash(payload), source_updated_at=None,
    )


def _is_xml_payload_error(error: Exception) -> bool:
    return isinstance(error, (UnicodeDecodeError, etree.XMLSyntaxError)) or (
        isinstance(error, RuntimeError) and str(error).startswith("디코딩 실패:")
    )

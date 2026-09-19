"""서식 표 행을 DB 레코드로 만들고 적재한다 (docs/decisions/0003, V33 company_table_row).

`form_tables` 가 표를 행 단위로 풀면, 여기서 각 행을 담은 표 청크의 근거 ID 를 붙인다. 근거 ID 는
청킹과 같은 좌표 규칙(절 번호·표 번호·행 범위)으로 재현하므로 청크를 다시 만들 필요가 없다.
적재는 기업 단위로 지우고 다시 넣는다. 부분 적재 상태를 만들지 않기 위해서다.
"""

from __future__ import annotations

from dataclasses import dataclass

from pipeline.business_report.doc import Document
from pipeline.business_report.form_tables import FormTable, form_tables
from pipeline.raw_sources.business_report import _is_xml_payload_error, table_chunk_ranges
from pipeline.raw_sources.chunking_profiles import ChunkingProfile
from pipeline.raw_sources.dart_archive import DartArchive, DartDocumentRef

RULE_VERSION = "form-tables-v1"


@dataclass(frozen=True)
class TableRowRecord:
    corp_code: str
    rcept_no: str
    table_index: int
    form_code: str
    section_title: str
    entity_scope: str | None
    unit: str | None
    header: list[str]
    row_no: int
    matrix_row: int
    col_no: int
    row_labels: list[str]
    column_key: str
    fiscal_year: int | None
    value_num: float | None
    value_text: str
    parse_status: str
    evidence_id: str | None

    def as_tuple(self) -> tuple:
        return (
            self.corp_code, self.rcept_no, self.table_index, self.form_code, self.section_title, self.entity_scope,
            self.unit, self.header, self.row_no, self.matrix_row, self.col_no, self.row_labels, self.column_key,
            self.fiscal_year, self.value_num, self.value_text, self.parse_status, self.evidence_id, RULE_VERSION,
        )


def document_records(document: Document, ref: DartDocumentRef, profile: ChunkingProfile) -> list[TableRowRecord]:
    """문서 하나의 서식 표 행. 근거 ID 는 행이 속한 청크(row_start ≤ matrix_row ≤ row_end)의 것."""
    ranges = table_chunk_ranges(document, ref, profile)
    records: list[TableRowRecord] = []
    for form in form_tables(document, report_year=ref.year):
        chunks = ranges.get(form.table_index, [])
        for row in form.rows:
            evidence_id = next((eid for start, end, eid in chunks if start <= row.matrix_row <= end), None)
            records.append(TableRowRecord(
                ref.corp_code, ref.rcept_no, form.table_index, form.form_code, form.section_title, form.entity_scope,
                form.unit, list(form.header), row.row_no, row.matrix_row, row.col_no, list(row.row_labels), row.column_key,
                row.fiscal_year, row.value_num, row.value_text, row.parse_status, evidence_id,
            ))
    return records


def company_records(
    archive: DartArchive, corp_code: str, profile: ChunkingProfile, failures: list[dict] | None = None,
) -> list[TableRowRecord]:
    """기업의 모든 보고서. 깨진 XML 은 청킹과 같은 기준으로 건너뛰고 `failures` 에 남긴다."""
    records: list[TableRowRecord] = []
    for ref in archive.documents(corp_code):
        try:
            document = Document.from_bytes(archive.read(ref), rcept_no=ref.rcept_no)
        except Exception as error:  # noqa: BLE001
            if not _is_xml_payload_error(error):
                raise
            if failures is not None:
                failures.append({"corp_code": corp_code, "rcept_no": ref.rcept_no, "reason": "xml_parse_error", "message": str(error)[:200]})
            continue
        records.extend(document_records(document, ref, profile))
    return records


_DELETE = "DELETE FROM company_table_row WHERE corp_code = %s"
_INSERT = """
INSERT INTO company_table_row
    (corp_code, rcept_no, table_index, form_code, section_title, entity_scope, unit, header,
     row_no, matrix_row, col_no, row_labels, column_key, fiscal_year, value_num, value_text,
     parse_status, evidence_id, rule_version)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


_COPY = """
COPY company_table_row
    (corp_code, rcept_no, table_index, form_code, section_title, entity_scope, unit, header,
     row_no, matrix_row, col_no, row_labels, column_key, fiscal_year, value_num, value_text,
     parse_status, evidence_id, rule_version)
FROM STDIN
"""


def write_company_rows(connection, corp_code: str, records: list[TableRowRecord]) -> dict[str, int]:
    """기업의 기존 행을 지우고 다시 넣는다. 근거 ID 가 rag_evidence 에 없으면 NULL 로 두고 건수를 보고한다."""
    cursor = connection.cursor()
    wanted = sorted({r.evidence_id for r in records if r.evidence_id})
    known: set[str] = set()
    if wanted:
        cursor.execute("SELECT evidence_id FROM rag_evidence WHERE evidence_id = ANY(%s)", (wanted,))
        known = {row[0] for row in cursor.fetchall()}
    rows = []
    unmatched = 0
    for record in records:
        evidence_id = record.evidence_id if record.evidence_id in known else None
        if record.evidence_id and evidence_id is None:
            unmatched += 1
        rows.append((*record.as_tuple()[:17], evidence_id, RULE_VERSION))
    cursor.execute(_DELETE, (corp_code,))
    if rows and hasattr(cursor, "copy"):
        # 5만 행 규모라 executemany(행당 왕복)보다 COPY 가 훨씬 빠르다. 실측: 772행 executemany 약 130초.
        with cursor.copy(_COPY) as copy:
            for row in rows:
                copy.write_row(row)
    elif rows:
        cursor.executemany(_INSERT, rows)
    return {
        "row_count": len(rows),
        "number_count": sum(1 for r in records if r.parse_status == "NUMBER"),
        "misaligned_count": sum(1 for r in records if r.parse_status == "MISALIGNED"),
        "table_count": len({(r.rcept_no, r.table_index) for r in records}),
        "evidence_unmatched": unmatched,
    }


def summarize(records: list[TableRowRecord]) -> dict[str, int]:
    return {
        "row_count": len(records),
        "number_count": sum(1 for r in records if r.parse_status == "NUMBER"),
        "misaligned_count": sum(1 for r in records if r.parse_status == "MISALIGNED"),
        "table_count": len({(r.rcept_no, r.table_index) for r in records}),
        "evidence_unmatched": sum(1 for r in records if r.evidence_id is None),
    }


def forms_of(records: list[TableRowRecord]) -> dict[str, int]:
    tables: dict[str, set[tuple[str, int]]] = {}
    for r in records:
        tables.setdefault(r.form_code, set()).add((r.rcept_no, r.table_index))
    return {code: len(v) for code, v in sorted(tables.items())}


__all__ = ["FormTable", "TableRowRecord", "RULE_VERSION", "document_records", "company_records", "write_company_rows", "summarize", "forms_of"]

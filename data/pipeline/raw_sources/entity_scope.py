"""원본 XML 표의 명시적 법인 제목을 기존 RAG 근거 ID에 연결한다."""
from __future__ import annotations

from pipeline.business_report.doc import Document

from .business_report import _is_xml_payload_error, scoped_table_evidence_ids
from .chunking_profiles import ChunkingProfile
from .dart_archive import DartArchive


def scope_rows(
    archive: DartArchive,
    corp_code: str,
    profile: ChunkingProfile,
) -> list[tuple[str, str, str, int]]:
    rows: list[tuple[str, str, str, int]] = []
    for ref in archive.documents(corp_code):
        try:
            document = Document.from_bytes(archive.read(ref), rcept_no=ref.rcept_no)
            evidence_ids = scoped_table_evidence_ids(document, ref, profile)
        except Exception as error:
            if not _is_xml_payload_error(error):
                raise
            continue
        scopes = {table.idx: table.entity_scope for table in document.tables}
        for table_index, evidence_id in evidence_ids:
            scope = scopes.get(table_index)
            if scope:
                rows.append((evidence_id, scope, ref.rcept_no, table_index))
    return sorted(rows, key=lambda row: (row[2], row[3], row[0]))

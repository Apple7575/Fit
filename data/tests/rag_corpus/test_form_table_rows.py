import tempfile
import unittest
from pathlib import Path

from pipeline.business_report.doc import Document
from pipeline.rag_corpus.form_table_rows import RULE_VERSION, company_records, document_records, forms_of, summarize, write_company_rows
from pipeline.raw_sources.business_report import business_report_batch, table_chunk_ranges
from pipeline.raw_sources.chunking_profiles import get_chunking_profile
from pipeline.raw_sources.dart_archive import DartArchive

from data.tests.raw_sources.test_business_report import make_archive

PAYLOAD = """<DOCUMENT><TITLE>1. 임원 및 직원 등의 현황</TITLE>
  <P>【 우리자산운용 】</P>
  <TABLE><THEAD><TR><TD>구 분</TD><TD>인원수</TD><TD>연간급여 총액</TD><TD>1인평균 급여액</TD><TD>비고</TD></TR></THEAD>
  <TBODY>
    <TR><TD>미등기임원</TD><TD>10</TD><TD>1,219</TD><TD>122</TD><TD>-</TD></TR>
  </TBODY></TABLE>
  <TITLE>3. 연결재무제표 주석</TITLE>
  <TABLE><TBODY><TR><TD>과목</TD><TD>당기말</TD></TR><TR><TD>리스자산</TD><TD>3,306,464</TD></TR></TBODY></TABLE>
</DOCUMENT>""".encode()


class FakeCursor:
    def __init__(self, known_ids):
        self.known_ids = set(known_ids)
        self.queries: list[tuple[str, object]] = []
        self.inserted: list[tuple] = []

    def execute(self, query, parameters=None):
        self.queries.append((query.strip().split()[0], parameters))
        if query.strip().startswith("SELECT"):
            self._matched = sorted(self.known_ids.intersection(parameters[0]))

    def fetchall(self):
        return [(evidence_id,) for evidence_id in self._matched]

    def executemany(self, _query, rows):
        self.inserted.extend(rows)


class FakeConnection:
    def __init__(self, known_ids):
        self.cursor_value = FakeCursor(known_ids)

    def cursor(self):
        return self.cursor_value


def _archive_and_profile(directory: str):
    archive_path = Path(directory) / "dart.zip"
    make_archive(archive_path, [(2024, "20250318000001", PAYLOAD)])
    return DartArchive(archive_path), get_chunking_profile("adaptive-v1")


class RecordsTest(unittest.TestCase):
    def test_rows_carry_the_chunk_evidence_id_and_entity_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            archive, profile = _archive_and_profile(directory)
            with archive:
                ref = archive.documents("00000001")[0]
                document = Document.from_bytes(archive.read(ref), rcept_no=ref.rcept_no)
                records = document_records(document, ref, profile)
                chunk_ids = {
                    row.metadata["table_index"]: row.evidence_id
                    for row in business_report_batch(archive, "00000001", profile=profile).records
                    if row.metadata["content_type"] == "TABLE"
                }
        self.assertTrue(records)
        self.assertEqual({r.form_code for r in records}, {"EXECUTIVE_PAY"}, "주석 표는 서식이 아니라 제외")
        first = records[0]
        self.assertEqual(first.evidence_id, chunk_ids[first.table_index], "행의 근거 ID 는 청킹과 같은 규칙으로 재현")
        self.assertEqual(first.entity_scope, "우리자산운용")
        self.assertEqual(first.unit, "백만원")
        by_key = {r.column_key: r for r in records}
        self.assertEqual(by_key["인원수"].value_num, 10.0)
        self.assertEqual(by_key["연간급여총액"].value_num, 1219.0)
        self.assertEqual(summarize(records)["evidence_unmatched"], 0)
        self.assertEqual(forms_of(records), {"EXECUTIVE_PAY": 1})

    def test_table_chunk_ranges_cover_every_table_once(self):
        with tempfile.TemporaryDirectory() as directory:
            archive, profile = _archive_and_profile(directory)
            with archive:
                ref = archive.documents("00000001")[0]
                document = Document.from_bytes(archive.read(ref), rcept_no=ref.rcept_no)
                ranges = table_chunk_ranges(document, ref, profile)
        self.assertEqual(sorted(ranges), [0, 1])
        self.assertEqual(ranges[0][0][:2], (0, 1))

    def test_company_records_reads_all_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            archive, profile = _archive_and_profile(directory)
            with archive:
                records = company_records(archive, "00000001", profile)
        self.assertEqual(len(records), 4, "본문 1행 × 값 열 4개(인원수·급여총액·평균급여·비고)")


class WriteTest(unittest.TestCase):
    def test_write_replaces_company_rows_and_nulls_unknown_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            archive, profile = _archive_and_profile(directory)
            with archive:
                records = company_records(archive, "00000001", profile)
        known = {records[0].evidence_id}
        connection = FakeConnection(known)
        result = write_company_rows(connection, "00000001", records)
        cursor = connection.cursor_value
        self.assertEqual([q for q, _ in cursor.queries], ["SELECT", "DELETE"], "기업 행을 지운 뒤 넣는다")
        self.assertEqual(cursor.queries[1][1], ("00000001",))
        self.assertEqual(len(cursor.inserted), 4)
        self.assertTrue(all(row[-1] == RULE_VERSION for row in cursor.inserted))
        self.assertTrue(all(row[-3] in known and row[-2] == "LINKED" for row in cursor.inserted))
        self.assertEqual(result["row_count"], 4)
        self.assertEqual(result["evidence_unmatched"], 0)

        missing = FakeConnection(set())
        result = write_company_rows(missing, "00000001", records)
        self.assertEqual(result["evidence_unmatched"], 4, "청크가 없으면 NULL 로 넣고 건수를 보고")
        self.assertTrue(all(row[-3] is None and row[-2] == "PENDING_CHUNK" for row in missing.cursor_value.inserted), "청크가 없으면 PENDING_CHUNK 로 구분해 보고서 인용을 막는다")


if __name__ == "__main__":
    unittest.main()

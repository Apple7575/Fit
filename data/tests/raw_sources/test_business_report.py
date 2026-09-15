import csv
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

from pipeline.business_report.doc import Document
from pipeline.raw_sources.business_report import business_report_batch
from pipeline.raw_sources.dart_archive import DartArchive


def make_archive(path: Path, documents: list[tuple[int, str, bytes]]) -> None:
    output = io.StringIO(newline="")
    fields = ["corp_name", "corp_code", "year", "rcept_no", "rcept_dt", "report_nm", "file"]
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    with zipfile.ZipFile(path, "w") as archive:
        for year, receipt, payload in documents:
            filename = f"document_{receipt}.xml"
            writer.writerow({
                "corp_name": "테스트전자", "corp_code": "00000001", "year": year,
                "rcept_no": receipt, "rcept_dt": "20250318",
                "report_nm": f"사업보고서 {year}", "file": filename,
            })
            archive.writestr(f"dart_local/cache/{filename}", payload)
        archive.writestr("dart_local/company_reports.csv", output.getvalue())


def build_batch(payload: bytes, *, max_chars: int = 1500):
    with tempfile.TemporaryDirectory() as directory:
        archive_path = Path(directory) / "dart.zip"
        make_archive(archive_path, [(2024, "20250318000001", payload)])
        with DartArchive(archive_path) as archive:
            return business_report_batch(archive, "00000001", max_chars=max_chars)


class BusinessReportSourceTest(unittest.TestCase):
    def test_document_constructor_accepts_existing_bytes_and_receipt_contract(self):
        from pipeline.business_report.extract import parse_one

        payload = "<DOCUMENT><TITLE>II</TITLE><P>본문</P></DOCUMENT>".encode()
        result = parse_one(payload, corp_code="00000001", fiscal_year=2024, rcept_no="20250318000001")

        self.assertFalse(result.failed)
        self.assertEqual(result.summary["rcept_no"], "20250318000001")

    def test_chunks_all_meaningful_sections_and_separates_tables(self):
        payload = """<DOCUMENT>
          <TITLE>I. 회사의 개요</TITLE><P>전자제품을 제조합니다.</P>
          <TITLE>목차</TITLE><P>1 2 3</P>
          <TITLE>II. 사업의 내용</TITLE><P>단위: 백만원</P>
          <TABLE><TR><TD>구분</TD><TD>2024</TD></TR>
                 <TR><TD>반도체</TD><TD>100</TD></TR></TABLE>
        </DOCUMENT>""".encode()

        batch = build_batch(payload)

        self.assertEqual({row.metadata["content_type"] for row in batch.records}, {"TEXT", "TABLE"})
        self.assertIn("I. 회사의 개요", {row.metadata["section_title"] for row in batch.records})
        self.assertNotIn("목차", {row.metadata["section_title"] for row in batch.records})
        table = next(row for row in batch.records if row.metadata["content_type"] == "TABLE")
        self.assertEqual(table.metadata["table_index"], 0)
        self.assertEqual(table.metadata["row_start"], 0)
        self.assertEqual(table.metadata["chunk_schema_version"], 2)
        self.assertIn("표 머리글: 구분 | 2024", table.content)

    def test_preserves_paragraph_coordinates_and_excludes_table_descendants(self):
        payload = """<DOCUMENT><TITLE>II. 사업의 내용</TITLE>
          <P></P><P>보이는 문단</P>
          <TABLE><TR><TD><P>표 내부 문단</P></TD><TD>100</TD></TR></TABLE>
        </DOCUMENT>""".encode()

        document = Document.from_bytes(payload, rcept_no="20250318000001")
        batch = build_batch(payload)
        text = next(row for row in batch.records if row.metadata["content_type"] == "TEXT")

        self.assertEqual(text.content, "보이는 문단")
        self.assertEqual((text.metadata["paragraph_start"], text.metadata["paragraph_end"]), (1, 1))
        self.assertEqual(document.sections[1].paragraphs, ["보이는 문단"])
        self.assertEqual(batch.excluded_counts["blank_content"], 1)
        self.assertFalse(any(
            row.metadata["content_type"] == "TEXT" and "표 내부 문단" in row.content
            for row in batch.records
        ))

    def test_splits_long_text_and_table_rows_under_character_limit_deterministically(self):
        payload = f"""<DOCUMENT><TITLE>II. 사업의 내용</TITLE><P>{'가' * 1700}</P>
          <TITLE>표</TITLE><P>표 설명</P><TABLE><TR><TD>구분</TD><TD>값1</TD><TD>값2</TD></TR>
          <TR><TD>제품</TD><TD>{'나' * 800}</TD><TD>{'다' * 800}</TD></TR></TABLE>
        </DOCUMENT>""".encode()

        first = build_batch(payload)
        second = build_batch(payload)
        tables = [row for row in first.records if row.metadata["content_type"] == "TABLE"]

        self.assertTrue(all(len(row.content) <= 1500 for row in first.records))
        self.assertEqual(
            [(row.source_identity, row.evidence_id, row.content_hash) for row in first.records],
            [(row.source_identity, row.evidence_id, row.content_hash) for row in second.records],
        )
        self.assertEqual([row.metadata["row_part_index"] for row in tables], [0, 1])
        self.assertTrue(all(row.metadata["row_part_count"] == 2 for row in tables))
        self.assertTrue(all("표 캡션: 표 설명" in row.content for row in tables))

    def test_skips_expansion_when_rowspan_or_colspan_exceeds_limit(self):
        payload = (
            "<DOCUMENT><TABLE><TR><TD COLSPAN='101'>header</TD></TR>"
            "<TR><TD ROWSPAN='101'>value</TD></TR></TABLE></DOCUMENT>"
        ).encode()

        document = Document.from_bytes(payload, rcept_no="20250318000001", max_table_cells=100)

        self.assertEqual(document.tables[0].m, [])
        self.assertEqual(document.tables[0].excluded_reason, "table_too_large")
        self.assertEqual(document.excluded_table_counts, {"table_too_large": 1})

    def test_skips_ragged_table_when_rectangular_grid_exceeds_limit(self):
        payload = (
            "<DOCUMENT><TABLE><TR><TD COLSPAN='100'>header</TD></TR><TR></TR>"
            "</TABLE></DOCUMENT>"
        ).encode()

        document = Document.from_bytes(payload, rcept_no="20250318000001", max_table_cells=100)

        self.assertEqual(document.tables[0].excluded_reason, "table_too_large")
        self.assertEqual(document.tables[0].m, [])

    def test_invalid_span_is_excluded_instead_of_reaching_matrix_conversion(self):
        payload = b"<DOCUMENT><TABLE><TR><TD COLSPAN='abc'>header</TD></TR></TABLE></DOCUMENT>"

        document = Document.from_bytes(payload, rcept_no="20250318000001")

        self.assertEqual(document.tables[0].excluded_reason, "table_invalid_span")
        self.assertEqual(document.excluded_table_counts, {"table_invalid_span": 1})

    def test_preserves_a_long_single_row_header_in_table_parts(self):
        header = "가" * 1700
        payload = f"<DOCUMENT><TABLE><TR><TD>{header}</TD></TR></TABLE></DOCUMENT>".encode()

        batch = build_batch(payload)
        tables = [row for row in batch.records if row.metadata["content_type"] == "TABLE"]
        ordered = sorted(tables, key=lambda row: row.metadata.get("row_part_index", -1))

        self.assertTrue(all(len(row.content) <= 1500 for row in tables))
        self.assertEqual("".join(row.content for row in ordered), f"표 캡션: \n표 머리글: {header}")
        self.assertTrue(all(row.metadata["row_start"] == 0 for row in tables))

    def test_keeps_identical_paragraphs_when_their_section_coordinates_differ(self):
        payload = (
            "<DOCUMENT><TITLE>첫 섹션</TITLE><P>같은 문장</P>"
            "<TITLE>둘째 섹션</TITLE><P>같은 문장</P></DOCUMENT>"
        ).encode()

        batch = build_batch(payload)
        texts = [row for row in batch.records if row.metadata["content_type"] == "TEXT"]

        self.assertEqual(len(texts), 2)
        self.assertEqual({row.metadata["section_title"] for row in texts}, {"첫 섹션", "둘째 섹션"})

    def test_rejects_character_limits_above_the_report_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "dart.zip"
            make_archive(archive_path, [(2024, "20250318000001", b"<DOCUMENT/>")])
            with DartArchive(archive_path) as archive:
                with self.assertRaisesRegex(ValueError, "1500 이하"):
                    business_report_batch(archive, "00000001", max_chars=1501)

    def test_keeps_valid_report_when_another_archive_member_is_broken(self):
        valid = "<DOCUMENT><TITLE>II. 사업의 내용</TITLE><P>정상 보고서</P></DOCUMENT>".encode()
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "dart.zip"
            make_archive(archive_path, [
                (2023, "20240318000001", b"<DOCUMENT>"),
                (2024, "20250318000001", valid),
            ])
            with DartArchive(archive_path) as archive:
                batch = business_report_batch(archive, "00000001")

        self.assertEqual(batch.failures[0]["reason"], "xml_parse_error")
        self.assertTrue(any("정상 보고서" in row.content for row in batch.records))


if __name__ == "__main__":
    unittest.main()

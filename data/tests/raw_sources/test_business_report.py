import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
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
        parts = sorted(
            [row for row in tables if row.metadata["row_start"] == 1],
            key=lambda row: row.metadata["row_part_index"],
        )
        self.assertEqual([row.metadata["row_part_index"] for row in parts], [0, 1])
        self.assertTrue(all(row.metadata["row_part_count"] == 2 for row in parts))
        self.assertTrue(all(row.metadata["row_format"] == "JSON_CELLS_V1" for row in parts))
        self.assertEqual(json.loads("".join(row.content for row in parts)), ["제품", "나" * 800, "다" * 800])

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

    def test_rejects_finite_huge_span_before_range_or_pending_expansion(self):
        payload = (
            "<DOCUMENT><TABLE><TR><TD COLSPAN='1000000000' ROWSPAN='2'>header</TD>"
            "</TR><TR></TR></TABLE></DOCUMENT>"
        ).encode()
        real_range = range

        def guarded_range(*args):
            if max(args) > 10_000:
                raise AssertionError("거대 span을 반복하면 안 됩니다")
            return real_range(*args)

        with patch("pipeline.business_report.doc.range", guarded_range, create=True):
            document = Document.from_bytes(payload, rcept_no="20250318000001")

        self.assertEqual(document.tables[0].excluded_reason, "table_too_large")
        self.assertEqual(document.tables[0].m, [])

    def test_matches_matrix_rowspan_lifetime_at_rectangular_limit(self):
        payload = (
            "<DOCUMENT><TABLE>"
            "<TR><TD COLSPAN='30000' ROWSPAN='2'>A</TD></TR>"
            "<TR><TD COLSPAN='30000' ROWSPAN='4'>B</TD></TR>"
            "<TR><TD COLSPAN='45000' ROWSPAN='1'>C</TD></TR>"
            "</TABLE></DOCUMENT>"
        ).encode()

        rejected = Document.from_bytes(payload, rcept_no="20250318000001", max_table_cells=224_999)
        accepted = Document.from_bytes(payload, rcept_no="20250318000001", max_table_cells=225_000)

        self.assertEqual(rejected.tables[0].excluded_reason, "table_too_large")
        self.assertIsNone(accepted.tables[0].excluded_reason)
        self.assertEqual((len(accepted.tables[0].m), len(accepted.tables[0].m[0])), (3, 75_000))

    def test_rejects_when_adjacent_pending_spans_require_multiple_skips(self):
        payload = (
            "<DOCUMENT><TABLE>"
            "<TR><TD COLSPAN='40000' ROWSPAN='3'>A</TD>"
            "<TD COLSPAN='40000' ROWSPAN='4'>B</TD></TR>"
            "<TR><TD COLSPAN='30000'>C</TD></TR>"
            "</TABLE></DOCUMENT>"
        ).encode()

        document = Document.from_bytes(payload, rcept_no="20250318000001", max_table_cells=200_000)

        self.assertEqual(document.tables[0].excluded_reason, "table_too_large")
        self.assertEqual(document.tables[0].m, [])

    def test_matches_matrix_when_new_rowspan_overwrites_later_pending_interval(self):
        payload = (
            "<DOCUMENT><TABLE>"
            "<TR><TD COLSPAN='2'>A</TD><TD COLSPAN='2' ROWSPAN='4'>B</TD></TR>"
            "<TR><TD COLSPAN='4' ROWSPAN='2'>C</TD></TR>"
            "<TR><TD>D</TD></TR>"
            "</TABLE></DOCUMENT>"
        ).encode()

        document = Document.from_bytes(payload, rcept_no="20250318000001", max_table_cells=12)

        self.assertIsNone(document.tables[0].excluded_reason)
        self.assertEqual(document.tables[0].m[2], ["D", "", "", ""])

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

    def test_long_context_rows_preserve_empty_cells_and_part_boundaries(self):
        header = "H" * 1500
        middle = "가" * 1600
        cells = ["", "100", "", middle, "200", ""]
        payload = (
            f"<DOCUMENT><TABLE><TR><TD>{header}</TD></TR><TR>"
            f"<TD></TD><TD>100</TD><TD></TD><TD>{middle}</TD><TD>200</TD><TD></TD>"
            "</TR></TABLE></DOCUMENT>"
        ).encode()

        batch = build_batch(payload)
        parts = sorted(
            [row for row in batch.records if row.metadata["content_type"] == "TABLE" and row.metadata["row_start"] == 1],
            key=lambda row: row.metadata["row_part_index"],
        )

        self.assertGreater(len(parts), 1)
        self.assertTrue(all(row.metadata["row_format"] == "JSON_CELLS_V1" for row in parts))
        self.assertEqual(json.loads("".join(row.content for row in parts)), cells)
        self.assertEqual([row.metadata["row_part_index"] for row in parts], list(range(len(parts))))
        self.assertTrue(all(row.metadata["row_part_count"] == len(parts) for row in parts))

    def test_short_context_long_row_preserves_empty_cells_and_column_positions(self):
        middle = "가" * 1600
        cells = ["", middle, "100", ""]
        payload = (
            "<DOCUMENT><TABLE><TR><TD>구분</TD><TD>값</TD></TR><TR>"
            f"<TD></TD><TD>{middle}</TD><TD>100</TD><TD></TD>"
            "</TR></TABLE></DOCUMENT>"
        ).encode()

        batch = build_batch(payload)
        parts = sorted(
            [row for row in batch.records if row.metadata["content_type"] == "TABLE" and row.metadata["row_start"] == 1],
            key=lambda row: row.metadata["row_part_index"],
        )

        self.assertGreater(len(parts), 1)
        self.assertTrue(all(row.metadata["row_format"] == "JSON_CELLS_V1" for row in parts))
        self.assertEqual(json.loads("".join(row.content for row in parts)), cells)
        self.assertEqual([row.metadata["row_part_index"] for row in parts], list(range(len(parts))))
        self.assertTrue(all(row.metadata["row_part_count"] == len(parts) for row in parts))

    def test_reports_truncated_xml_as_source_failure_instead_of_recovering_partial_content(self):
        batch = build_batch("<DOCUMENT><TITLE>사업</TITLE><P>남아 있는 본문</P>".encode())

        self.assertEqual(batch.records, [])
        self.assertEqual(batch.failures[0]["reason"], "xml_parse_error")

    def test_rejects_large_merged_cell_text_before_matrix_expansion(self):
        payload = ("<DOCUMENT><TABLE><TR><TD COLSPAN='100000'>" + "가" * 10_000 +
                   "</TD></TR></TABLE></DOCUMENT>").encode()

        with patch("pipeline.business_report.doc.matrix", side_effect=AssertionError("matrix must not run")):
            document = Document.from_bytes(payload, rcept_no="20250318000001")

        self.assertEqual(document.tables[0].excluded_reason, "table_too_large")
        self.assertEqual(document.tables[0].m, [])

    def test_allows_merged_cell_at_character_budget_boundary(self):
        payload = ("<DOCUMENT><TABLE><TR><TD COLSPAN='100'>" + "가" * 100 +
                   "</TD></TR></TABLE></DOCUMENT>").encode()

        document = Document.from_bytes(
            payload, rcept_no="20250318000001", max_table_cells=100, max_table_expanded_chars=10_000,
        )

        self.assertIsNone(document.tables[0].excluded_reason)
        self.assertEqual(document.tables[0].m, [["가" * 100] * 100])

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

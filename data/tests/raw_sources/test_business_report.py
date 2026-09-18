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
from pipeline.raw_sources.chunking_profiles import get_chunking_profile
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
    def test_table_entity_scope_follows_explicit_heading_and_resets_at_title(self):
        payload = """<DOCUMENT><TITLE>3. 재무상태 및 영업실적</TITLE>
          <P>【 우리자산운용 】</P>
          <TABLE><TR><TD>영업이익</TD><TD>22,133</TD></TR></TABLE>
          <P>단위: 백만원</P>
          <TABLE><TR><TD>매출</TD><TD>64,547</TD></TR></TABLE>
          <P>【 우리은행 】</P>
          <TABLE><TR><TD>영업이익</TD><TD>3,520,741</TD></TR></TABLE>
          <TITLE>4. 다음 장</TITLE>
          <TABLE><TR><TD>영업이익</TD><TD>100</TD></TR></TABLE>
        </DOCUMENT>""".encode()

        document = Document(payload, rcept_no="20260313001235")

        self.assertEqual(
            [table.entity_scope for table in document.tables],
            ["우리자산운용", "우리자산운용", "우리은행", None],
        )

    def test_generic_bracket_heading_is_not_a_company_name(self):
        payload = """<DOCUMENT><TITLE>영업실적</TITLE>
          <P>【 자산운용업: 우리자산운용 】</P>
          <TABLE><TR><TD>영업이익</TD><TD>22,133</TD></TR></TABLE>
          <P>【 은행계정 】</P>
          <TABLE><TR><TD>수익</TD><TD>1,000</TD></TR></TABLE>
        </DOCUMENT>""".encode()

        document = Document(payload, rcept_no="20260313001235")

        self.assertEqual([table.entity_scope for table in document.tables],
                         ["우리자산운용", "우리자산운용"])

    def test_group_category_heading_does_not_create_entity_scope(self):
        payload = """<DOCUMENT><TITLE>실적</TITLE>
          <P>【 은행 주요 자회사의 현황 】</P>
          <TABLE><TR><TD>영업이익</TD><TD>22,133</TD></TR></TABLE>
        </DOCUMENT>""".encode()

        document = Document(payload, rcept_no="20260313001235")

        self.assertIsNone(document.tables[0].entity_scope)

    def test_group_category_heading_ends_previous_entity_scope(self):
        payload = """<DOCUMENT><TITLE>실적</TITLE>
          <P>【 우리은행 】</P>
          <TABLE><TR><TD>영업이익</TD><TD>100</TD></TR></TABLE>
          <P>【 은행 주요 자회사의 현황 】</P>
          <TABLE><TR><TD>영업이익</TD><TD>200</TD></TR></TABLE>
        </DOCUMENT>""".encode()

        document = Document(payload, rcept_no="20260313001235")

        self.assertEqual([table.entity_scope for table in document.tables], ["우리은행", None])

    def test_profile_controls_text_and_table_limits_and_evidence_identity(self):
        payload = (
            "<DOCUMENT><TITLE>사업</TITLE><P>" + "가" * 1600 + "</P>"
            "<TABLE><TR><TD>구분</TD><TD>값</TD></TR><TR><TD>항목</TD><TD>" + "나" * 1600
            + "</TD></TR></TABLE></DOCUMENT>"
        ).encode()
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "dart.zip"
            make_archive(archive_path, [(2024, "20250318000001", payload)])
            with DartArchive(archive_path) as archive:
                compact = business_report_batch(
                    archive, "00000001", profile=get_chunking_profile("structural-800-v1"),
                )
                adaptive = business_report_batch(
                    archive, "00000001", profile=get_chunking_profile("adaptive-v1"),
                )

        self.assertTrue(all(len(row.content) <= 800 for row in compact.records))
        self.assertTrue(all(
            len(row.content) <= (1200 if row.metadata["content_type"] == "TEXT" else 800)
            for row in adaptive.records
        ))
        self.assertTrue(all(row.metadata["chunking_profile"] == "adaptive-v1" for row in adaptive.records))
        self.assertNotEqual(
            {row.evidence_id for row in compact.records},
            {row.evidence_id for row in adaptive.records},
        )

    def test_rowspan_covers_every_row_it_declares(self):
        # 우리금융지주 20260313001235 표 825: `영업이익 ROWSPAN=4`가 3행만 덮어 `판매관리비` 행 값이 한 칸 밀렸다.
        payload = """<DOCUMENT><TITLE>6. 영업부문 (연결)</TITLE>
          <TABLE>
            <TR><TH></TH><TH></TH><TH>은행</TH><TH>보험</TH><TH>카드</TH></TR>
            <TR><TE COLSPAN="2">영업이익</TE><TE>3,520,741</TE><TE>108,040</TE><TE>213,556</TE></TR>
            <TR><TE ROWSPAN="4">영업이익</TE><TE>순이자손익</TE><TE>6,807,324</TE><TE>(105,758)</TE><TE>756,173</TE></TR>
            <TR><TE>비이자손익</TE><TE>2,133,050</TE><TE>271,296</TE><TE>212,462</TE></TR>
            <TR><TE>신용손실</TE><TE>(1,126,171)</TE><TE>(5,833)</TE><TE>(433,302)</TE></TR>
            <TR><TE>판매관리비</TE><TE>(4,293,462)</TE><TE>(51,665)</TE><TE>(321,777)</TE></TR>
            <TR><TE COLSPAN="2">영업외손익</TE><TE>(161,553)</TE><TE>3,075</TE><TE>(18,316)</TE></TR>
          </TABLE></DOCUMENT>""".encode()

        document = Document(payload, rcept_no="20260313001235")

        rows = document.tables[0].m
        self.assertEqual(rows[5], ["영업이익", "판매관리비", "(4,293,462)", "(51,665)", "(321,777)"])
        self.assertEqual(rows[6], ["영업외손익", "영업외손익", "(161,553)", "3,075", "(18,316)"])
        self.assertTrue(all(len(row) == 5 for row in rows))

    def test_rowspan_two_covers_the_next_row(self):
        # 나노솔루션 20260728000338 매출 표: `기타 품목 COLSPAN=2 ROWSPAN=2`가 다음 행을 덮지 않아
        # `국 내 | 직납 | 229,577 (3.7%) | | `로 밀렸다.
        payload = """<DOCUMENT><TITLE>4. 매출 및 수주상황</TITLE>
          <TABLE>
            <TR><TH>매출유형</TH><TH>품 목</TH><TH>구 분</TH><TH>판매경로</TH><TH>판매경로별 매출액(비중)</TH></TR>
            <TR><TD>제품</TD><TD>SAHD30</TD><TD>국 내</TD><TD>직납</TD><TD>4,452,074 (71.3%)</TD></TR>
            <TR><TD COLSPAN="2" ROWSPAN="2">기타 품목</TD><TD>수 출</TD><TD>직납</TD><TD>62,779 (1.0%) (USD 43,709)</TD></TR>
            <TR><TD>국 내</TD><TD>직납</TD><TD>229,577 (3.7%)</TD></TR>
            <TR><TD COLSPAN="4">합 계</TD><TD>6,244,430 (100%)</TD></TR>
          </TABLE></DOCUMENT>""".encode()

        document = Document(payload, rcept_no="20260728000338")

        rows = document.tables[0].m
        self.assertEqual(rows[3], ["기타 품목", "기타 품목", "국 내", "직납", "229,577 (3.7%)"])
        self.assertEqual(rows[4], ["합 계", "합 계", "합 계", "합 계", "6,244,430 (100%)"])

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

    def test_does_not_repeat_text_from_nested_text_tags(self):
        payload = (
            "<DOCUMENT><TITLE>II. 사업의 내용</TITLE>"
            "<P><SPAN>첫 번째 문장</SPAN><SPAN>두 번째 문장</SPAN></P></DOCUMENT>"
        ).encode()

        document = Document.from_bytes(payload, rcept_no="20250318000001")

        self.assertEqual(document.sections[1].paragraphs, ["첫 번째 문장두 번째 문장"])

    def test_excludes_nested_table_container_and_keeps_leaf_table_coordinates(self):
        payload = """<DOCUMENT><TITLE>II. 사업의 내용</TITLE><P>매출 표</P>
          <TABLE><TR><TD>레이아웃
            <TABLE><TR><TD>구분</TD><TD>2024</TD></TR>
              <TR><TD>반도체</TD><TD>100</TD></TR></TABLE>
          </TD></TR></TABLE>
        </DOCUMENT>""".encode()

        document = Document.from_bytes(payload, rcept_no="20250318000001")
        batch = build_batch(payload)
        tables = [row for row in batch.records if row.metadata["content_type"] == "TABLE"]

        self.assertEqual(len(document.tables), 2)
        self.assertEqual(document.tables[0].excluded_reason, "nested_table_container")
        self.assertIsNone(document.tables[1].excluded_reason)
        self.assertEqual(document.excluded_table_counts, {"nested_table_container": 1})
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0].metadata["table_index"], 1)
        self.assertIn("반도체 | 100", tables[0].content)

    def test_excludes_identical_tables_within_the_same_section(self):
        table = (
            "<TABLE><TR><TD>구분</TD><TD>2024</TD></TR>"
            "<TR><TD>반도체</TD><TD>100</TD></TR></TABLE>"
        )
        batch = build_batch(f"<DOCUMENT><TITLE>사업</TITLE>{table}{table}</DOCUMENT>".encode())
        tables = [row for row in batch.records if row.metadata["content_type"] == "TABLE"]

        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0].metadata["table_index"], 0)
        self.assertEqual(batch.excluded_counts["duplicate_table_content"], 1)

    def test_keeps_identical_tables_when_section_lineage_differs(self):
        table = (
            "<TABLE><TR><TD>구분</TD><TD>2024</TD></TR>"
            "<TR><TD>반도체</TD><TD>100</TD></TR></TABLE>"
        )
        payload = (
            f"<DOCUMENT><TITLE>첫 섹션</TITLE>{table}"
            f"<TITLE>둘째 섹션</TITLE>{table}</DOCUMENT>"
        ).encode()

        batch = build_batch(payload)
        tables = [row for row in batch.records if row.metadata["content_type"] == "TABLE"]

        self.assertEqual(len(tables), 2)
        self.assertEqual({row.metadata["section_index"] for row in tables}, {1, 2})
        self.assertNotIn("duplicate_table_content", batch.excluded_counts)

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

        # A(rowspan 2)가 1행까지, B(rowspan 4)가 1~3행을 덮으므로 C는 0열부터 시작해 폭은 60,000이다.
        rejected = Document.from_bytes(payload, rcept_no="20250318000001", max_table_cells=179_999)
        accepted = Document.from_bytes(payload, rcept_no="20250318000001", max_table_cells=180_000)

        self.assertEqual(rejected.tables[0].excluded_reason, "table_too_large")
        self.assertIsNone(accepted.tables[0].excluded_reason)
        self.assertEqual((len(accepted.tables[0].m), len(accepted.tables[0].m[0])), (3, 60_000))

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

        # C(rowspan 2)가 2행의 0~3열을 덮으므로 D는 4열로 밀려 표 폭은 5, 셀 수는 15다.
        document = Document.from_bytes(payload, rcept_no="20250318000001", max_table_cells=15)
        rejected = Document.from_bytes(payload, rcept_no="20250318000001", max_table_cells=14)

        self.assertIsNone(document.tables[0].excluded_reason)
        self.assertEqual(document.tables[0].m[2], ["C", "C", "C", "C", "D"])
        self.assertEqual(rejected.tables[0].excluded_reason, "table_too_large")

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

    def test_rejects_fake_document_closing_tag_inside_unclosed_comment(self):
        batch = build_batch(b"<DOCUMENT><P>body</P><!-- </DOCUMENT>")

        self.assertEqual(batch.records, [])
        self.assertEqual(batch.failures[0]["reason"], "xml_parse_error")

    def test_rejects_fake_document_closing_tag_inside_unclosed_cdata(self):
        batch = build_batch(b"<DOCUMENT><P>body</P><![CDATA[ </DOCUMENT>")

        self.assertEqual(batch.records, [])
        self.assertEqual(batch.failures[0]["reason"], "xml_parse_error")

    def test_rejects_fake_document_closing_tag_inside_processing_instruction(self):
        batch = build_batch(b"<DOCUMENT><P>body</P><?parser </DOCUMENT>")

        self.assertEqual(batch.records, [])
        self.assertEqual(batch.failures[0]["reason"], "xml_parse_error")

    def test_rejects_fake_document_closing_tag_inside_unclosed_attribute_quote(self):
        batch = build_batch(b'<DOCUMENT><P marker="</DOCUMENT>')

        self.assertEqual(batch.records, [])
        self.assertTrue(batch.failures)
        self.assertEqual(batch.failures[0]["reason"], "xml_parse_error")

    def test_accepts_actual_document_closing_tag_after_lexical_constructs(self):
        payload = (
            b'<DOCUMENT><P marker="value">body</P><!-- note -->'
            b'<![CDATA[data]]><?parser done?></DOCUMENT>'
        )

        batch = build_batch(payload)

        self.assertEqual(batch.failures, ())
        self.assertTrue(any(record.content == "body" for record in batch.records))

    def test_accepts_outer_document_closing_tag_after_nested_document(self):
        batch = build_batch(b"<DOCUMENT><DOCUMENT><P>body</P></DOCUMENT></DOCUMENT>")

        self.assertEqual(batch.failures, ())
        self.assertTrue(any(record.content == "body" for record in batch.records))

    def test_accepts_doctype_with_comment_brackets(self):
        payload = b"<!DOCTYPE DOCUMENT [<!-- [ -->]><DOCUMENT><P>body</P></DOCUMENT>"

        batch = build_batch(payload)

        self.assertEqual(batch.failures, ())
        self.assertTrue(any(record.content == "body" for record in batch.records))

    def test_accepts_doctype_with_comment_quote(self):
        payload = b'<!DOCTYPE DOCUMENT [<!-- " -->]><DOCUMENT><P>body</P></DOCUMENT>'

        batch = build_batch(payload)

        self.assertEqual(batch.failures, ())
        self.assertTrue(any(record.content == "body" for record in batch.records))

    def test_recovers_closed_document_with_nonstandard_entities_for_rag(self):
        payload = (
            b"<DOCUMENT><TITLE>Overview &amp; Notes</TITLE>"
            b"<P>R&amp;D &unknown; & raw data</P></DOCUMENT>"
        )

        batch = build_batch(payload)

        self.assertEqual(batch.failures, ())
        self.assertTrue(any("R&D" in record.content for record in batch.records))

    def test_allows_whitespace_after_closed_document_with_recoverable_markup(self):
        payload = b"<DOCUMENT><P>R&amp;D &unknown; data</P></DOCUMENT> \r\n\t"

        batch = build_batch(payload)

        self.assertEqual(batch.failures, ())
        self.assertTrue(any("R&D" in record.content for record in batch.records))

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

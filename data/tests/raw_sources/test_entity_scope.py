import tempfile
import unittest
from pathlib import Path

from pipeline.raw_sources.business_report import business_report_batch, scoped_table_evidence_ids
from pipeline.raw_sources.chunking_profiles import get_chunking_profile
from pipeline.raw_sources.dart_archive import DartArchive
from pipeline.raw_sources.entity_scope import scope_rows

from data.tests.raw_sources.test_business_report import make_archive


class EntityScopeTest(unittest.TestCase):
    def test_table_only_evidence_ids_match_full_chunking_for_scoped_tables(self):
        payload = ("""<DOCUMENT><TITLE>3. 재무상태 및 영업실적</TITLE>
          <P>긴 본문 """ + ("가" * 4000) + """</P>
          <P>【 우리자산운용 】</P>
          <TABLE><TR><TD>영업이익</TD><TD>22,133</TD></TR></TABLE>
          <P>【 우리은행 】</P>
          <TABLE><TR><TD>영업이익</TD><TD>3,520,741</TD></TR></TABLE>
        </DOCUMENT>""").encode()
        profile = get_chunking_profile("adaptive-v1")
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "dart.zip"
            make_archive(archive_path, [(2024, "20250318000001", payload)])
            with DartArchive(archive_path) as archive:
                existing = business_report_batch(archive, "00000001", profile=profile)
                ref = archive.documents("00000001")[0]
                from pipeline.business_report.doc import Document
                document = Document.from_bytes(archive.read(ref), rcept_no=ref.rcept_no)
                actual = dict(scoped_table_evidence_ids(document, ref, profile))

        expected = {
            row.metadata["table_index"]: row.evidence_id
            for row in existing.records
            if row.metadata["content_type"] == "TABLE"
        }
        self.assertEqual(actual, {0: expected[0], 1: expected[1]})

    def test_scope_rows_match_existing_evidence_ids_without_changing_records(self):
        payload = """<DOCUMENT><TITLE>3. 재무상태 및 영업실적</TITLE>
          <P>【 우리자산운용 】</P>
          <TABLE><TR><TD>영업이익</TD><TD>22,133</TD></TR></TABLE>
          <P>【 우리은행 】</P>
          <TABLE><TR><TD>영업이익</TD><TD>3,520,741</TD></TR></TABLE>
          <TITLE>4. 기타</TITLE>
          <TABLE><TR><TD>영업이익</TD><TD>100</TD></TR></TABLE>
        </DOCUMENT>""".encode()
        profile = get_chunking_profile("adaptive-v1")
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "dart.zip"
            make_archive(archive_path, [(2024, "20250318000001", payload)])
            with DartArchive(archive_path) as archive:
                existing = business_report_batch(archive, "00000001", profile=profile)
                scoped = scope_rows(archive, "00000001", profile)

        table_by_index = {
            row.metadata["table_index"]: row
            for row in existing.records
            if row.metadata["content_type"] == "TABLE"
        }
        self.assertEqual(
            scoped,
            [
                (table_by_index[0].evidence_id, "우리자산운용", "20250318000001", 0),
                (table_by_index[1].evidence_id, "우리은행", "20250318000001", 1),
            ],
        )
        self.assertNotIn(table_by_index[2].evidence_id, {row[0] for row in scoped})


if __name__ == "__main__":
    unittest.main()

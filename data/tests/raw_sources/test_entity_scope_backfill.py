import unittest
import tempfile
from pathlib import Path

from data.scripts.backfill_rag_entity_scope import collect_company_scope_rows, write_scope_rows
from data.tests.raw_sources.test_business_report import make_archive


class FakeCursor:
    def __init__(self, known_ids):
        self.known_ids = set(known_ids)
        self.saved = {}
        self._matched = 0

    def execute(self, _query, parameters):
        self._matched = sorted(self.known_ids.intersection(parameters[0]))

    def fetchall(self):
        return [(evidence_id,) for evidence_id in self._matched]

    def executemany(self, _query, parameters):
        for evidence_id, scope_name, rcept_no, table_index in parameters:
            if evidence_id in self.known_ids:
                self.saved[evidence_id] = (scope_name, rcept_no, table_index)


class FakeConnection:
    def __init__(self, known_ids):
        self.cursor_value = FakeCursor(known_ids)

    def cursor(self):
        return self.cursor_value


class EntityScopeBackfillTest(unittest.TestCase):
    def test_collect_company_scope_rows_returns_rows_in_corp_code_order(self):
        payload = b"""<DOCUMENT><TITLE>3. \xec\x9e\xac\xeb\xac\xb4</TITLE>
        <P>\xe3\x80\x90 \xec\x9a\xb0\xeb\xa6\xac\xec\x9e\x90\xec\x82\xb0\xec\x9a\xb4\xec\x9a\xa9 \xe3\x80\x91</P>
        <TABLE><TR><TD>\xec\x98\x81\xec\x97\x85\xec\x9d\xb4\xec\x9d\xb5</TD><TD>22,133</TD></TR></TABLE></DOCUMENT>"""
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "dart.zip"
            make_archive(archive_path, [(2024, "20250318000001", payload)])
            actual = collect_company_scope_rows(
                archive_path, ["00000001"], "adaptive-v1", workers=2,
            )

        self.assertEqual(actual[0][0], "00000001")
        self.assertEqual(len(actual[0][1]), 1)

    def test_backfill_is_idempotent_and_reports_missing_evidence(self):
        connection = FakeConnection({"existing"})
        rows = [
            ("existing", "우리자산운용", "20260313001235", 3589),
            ("missing", "우리은행", "20260313001235", 3590),
        ]

        first = write_scope_rows(connection, rows)
        second = write_scope_rows(connection, rows)

        self.assertEqual(first, {"candidate_count": 2, "matched_count": 1, "missing_count": 1})
        self.assertEqual(second, first)
        self.assertEqual(connection.cursor_value.saved, {
            "existing": ("우리자산운용", "20260313001235", 3589),
        })


if __name__ == "__main__":
    unittest.main()

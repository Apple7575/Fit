from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "backend/src/main/resources/db/migration/V25__rag_business_report_evidence.sql"


class RagExternalEvidenceSchemaTest(unittest.TestCase):
    def test_extends_source_type_for_business_reports_only(self):
        sql = MIGRATION.read_text(encoding="utf-8")

        self.assertIn("DROP CONSTRAINT rag_evidence_source_type_check", sql)
        self.assertIn("DART_BUSINESS_REPORT", sql)
        self.assertNotIn("NEWS", sql)


if __name__ == "__main__":
    unittest.main()

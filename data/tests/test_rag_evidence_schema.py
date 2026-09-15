from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "backend/src/main/resources/db/migration/V24__rag_evidence.sql"


class RagEvidenceSchemaTest(unittest.TestCase):
    def test_schema_has_lineage_quality_and_lookup_contract(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        for fragment in (
            "CREATE TABLE rag_evidence",
            "evidence_id",
            "source_identity",
            "content_hash",
            "published_at",
            "quality",
            "REFERENCES company (corp_code)",
            "UNIQUE (source_identity)",
            "rag_evidence_company_published_idx",
            "rag_evidence_company_source_published_idx",
        ):
            self.assertIn(fragment, sql)

    def test_schema_does_not_require_pgvector(self):
        sql = MIGRATION.read_text(encoding="utf-8").lower()
        self.assertNotIn("create extension", sql)
        self.assertNotIn(" vector(", sql)


if __name__ == "__main__":
    unittest.main()

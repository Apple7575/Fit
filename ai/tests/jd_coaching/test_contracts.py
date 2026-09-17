import json
import tempfile
import unittest
from pathlib import Path

from ai.jd_coaching.contracts import DataContractError, load_jd_document


FIXTURE = {
    "schema_version": "1.0",
    "document_id": "samsung-ds-software-job-intro-2026-09-12",
    "company_name": "삼성전자",
    "organization": "DS부문",
    "job_title": "S/W 개발",
    "source_type": "OFFICIAL_JOB_DESCRIPTION",
    "source_url": "https://www.samsungcareers.com/subsid/detail/C10CAH",
    "retrieved_at": "2026-09-12",
    "published_at": None,
    "valid_until": None,
    "source_status": "ACCESSIBLE",
    "sections": [
        {
            "section_id": "job-summary-01",
            "section_type": "JOB_SUMMARY",
            "ordinal": 1,
            "text": "S/W기술에 관한 지식을 바탕으로 반도체가 활용된 Solution 제품을 연구/개발 하는 직무.",
        }
    ],
}


class JdDocumentContractTest(unittest.TestCase):
    def _write(self, payload: dict) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "document.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def test_loads_valid_document(self):
        document = load_jd_document(self._write(FIXTURE))

        self.assertEqual(document.document_id, FIXTURE["document_id"])
        self.assertEqual(document.sections[0].section_type, "JOB_SUMMARY")

    def test_rejects_duplicate_section_ids(self):
        payload = dict(FIXTURE)
        payload["sections"] = [FIXTURE["sections"][0], FIXTURE["sections"][0]]

        with self.assertRaisesRegex(DataContractError, "section_id"):
            load_jd_document(self._write(payload))

    def test_rejects_unknown_source_type(self):
        payload = dict(FIXTURE, source_type="BLOG_POST")

        with self.assertRaisesRegex(DataContractError, "source_type"):
            load_jd_document(self._write(payload))

    def test_rejects_non_https_source(self):
        payload = dict(FIXTURE, source_url="http://example.com/job")

        with self.assertRaisesRegex(DataContractError, "source_url"):
            load_jd_document(self._write(payload))

    def test_rejects_invalid_date_order(self):
        payload = dict(
            FIXTURE,
            published_at="2026-09-15",
            valid_until="2026-09-08",
        )

        with self.assertRaisesRegex(DataContractError, "valid_until"):
            load_jd_document(self._write(payload))

    def test_rejects_blank_section_text(self):
        payload = dict(FIXTURE)
        payload["sections"] = [dict(FIXTURE["sections"][0], text="  ")]

        with self.assertRaisesRegex(DataContractError, "text"):
            load_jd_document(self._write(payload))

    def test_preserves_pdf_source_metadata(self):
        payload = dict(
            FIXTURE,
            source_file_name="job-description.pdf",
            source_file_sha256="a" * 64,
        )
        payload["sections"] = [
            {**FIXTURE["sections"][0], "source_page": 52}
        ]

        document = load_jd_document(self._write(payload))

        self.assertEqual(document.source_file_name, "job-description.pdf")
        self.assertEqual(document.source_file_sha256, "a" * 64)
        self.assertEqual(document.sections[0].source_page, 52)

    def test_committed_source_documents_follow_contract(self):
        source_directory = (
            Path(__file__).parents[2] / "evals" / "jd_coaching" / "sources"
        )
        source_paths = sorted(source_directory.glob("*.json"))

        self.assertGreaterEqual(len(source_paths), 2)
        documents = [load_jd_document(path) for path in source_paths]
        self.assertTrue(
            {"OFFICIAL_JOB_DESCRIPTION", "TALENT_PROFILE"}.issubset(
                {document.source_type for document in documents}
            )
        )

    def test_json_schema_is_valid_json(self):
        schema_path = (
            Path(__file__).parents[2]
            / "jd_coaching"
            / "resources"
            / "schemas"
            / "jd-document-v1.json"
        )

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(schema["$id"], "jd-document-v1.json")


if __name__ == "__main__":
    unittest.main()

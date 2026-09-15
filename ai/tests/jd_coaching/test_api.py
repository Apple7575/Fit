import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from ai.jd_coaching.analysis_store import InMemoryAnalysisStore
from ai.jd_coaching.api import (
    app,
    get_analysis_service,
    get_analysis_store,
    get_source_ingestor,
    _required_database_url,
)
from ai.jd_coaching.source_ingestion import IngestedJd
from ai.jd_coaching.source_ingestion import UnsupportedSourceError


class FakeService:
    def create_context(self, **kwargs):
        return {
            "context_id": "jctx_test",
            **kwargs,
            "requirements": [],
            "created_at": "2026-09-13T00:00:00+00:00",
            "cache_hit": False,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    def get_context(self, context_id):
        if context_id == "missing":
            raise KeyError(context_id)
        return self.create_context(
            company_name="다른기업",
            position_name="백엔드 개발자",
            jd_text="Python 기반 API 개발 경험을 요구합니다.",
        )

    def analyze_documents(self, context_id, documents):
        return {
            "context_id": context_id,
            "company_name": "다른기업",
            "position_name": "백엔드 개발자",
            "requirements": [],
            "failed_requirements": [],
            "summary": {
                "supported": 0,
                "partially_supported": 0,
                "not_supported": 0,
                "failed": 0,
            },
            "model": "test-qwen",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    def analyze(self, **kwargs):
        return {
            "company_name": kwargs["company_name"],
            "position_name": kwargs["position_name"],
            "requirements": [],
            "summary": {
                "supported": 0,
                "partially_supported": 0,
                "not_supported": 0,
            },
            "model": "test-qwen",
            "usage": {"total_tokens": 0},
        }


class FakeSourceIngestor:
    def from_url(self, url):
        if url.endswith("/without-metadata"):
            return IngestedJd(
                jd_text="Python 기반 API 개발 경험을 요구합니다.",
                source_url=url,
            )
        return IngestedJd(
            jd_text="Python 기반 API 개발 경험을 요구합니다.",
            source_url=url,
            company_name="URL기업",
            position_name="백엔드 개발자",
            job_posting_id="url-posting-1",
            published_at="2026-09-01",
            valid_until="2026-09-30",
        )

    def from_file(self, *, filename, content_type, content):
        if filename.endswith(".png"):
            raise UnsupportedSourceError("지원하지 않는 파일 형식입니다: .png")
        return IngestedJd(
            jd_text=content.decode("utf-8"),
            filename=filename,
            content_sha256="a" * 64,
        )


class ApiTest(unittest.TestCase):
    def test_committed_openapi_uses_current_sync_analysis_path(self):
        committed = json.loads(
            Path("ai/docs/jd-coaching-openapi.json").read_text(encoding="utf-8")
        )

        self.assertIn("/internal/analyses", committed["paths"])
        self.assertNotIn("/internal/jd/analyze", committed["paths"])

    def setUp(self):
        self.analysis_store = InMemoryAnalysisStore()
        app.dependency_overrides[get_analysis_service] = lambda: FakeService()
        app.dependency_overrides[get_analysis_store] = lambda: self.analysis_store
        app.dependency_overrides[get_source_ingestor] = lambda: FakeSourceIngestor()
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_health(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_requires_postgresql_url_for_runtime_storage(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "JD_DATABASE_URL"):
                _required_database_url()

        with patch.dict(
            "os.environ", {"JD_DATABASE_URL": "sqlite:///runtime.db"}, clear=True
        ):
            with self.assertRaisesRegex(RuntimeError, "PostgreSQL"):
                _required_database_url()

        with patch.dict(
            "os.environ",
            {"JD_DATABASE_URL": "postgresql://user:pass@postgres:5432/app"},
            clear=True,
        ):
            self.assertEqual(
                _required_database_url(),
                "postgresql://user:pass@postgres:5432/app",
            )

    def test_reads_postgresql_url_from_ai_env_file(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "JD_DATABASE_URL=postgresql://user:pass@postgres:5432/app\n",
                encoding="utf-8",
            )
            with patch.dict(
                "os.environ",
                {"JD_QWEN_ENV_FILE": str(env_file)},
                clear=True,
            ):
                self.assertEqual(
                    _required_database_url(),
                    "postgresql://user:pass@postgres:5432/app",
                )

    def test_analyzes_user_supplied_jd(self):
        response = self.client.post(
            "/internal/analyses",
            json={
                "company_name": "다른기업",
                "position_name": "백엔드 개발자",
                "jd_text": "Python 기반 API 개발 경험을 요구합니다.",
                "applicant_text": "Python으로 배치 프로그램을 개발했습니다.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["company_name"], "다른기업")

    def test_does_not_expose_legacy_sync_analysis_path(self):
        response = self.client.post(
            "/internal/jd/analyze",
            json={
                "company_name": "다른기업",
                "position_name": "백엔드 개발자",
                "jd_text": "Python 기반 API 개발 경험을 요구합니다.",
                "applicant_text": "Python으로 API를 개발했습니다.",
            },
        )

        self.assertEqual(response.status_code, 404)

    def test_creates_and_reads_job_context(self):
        created = self.client.post(
            "/internal/job-contexts",
            json={
                "company_name": "다른기업",
                "position_name": "백엔드 개발자",
                "jd_text": "Python 기반 API 개발 경험을 요구합니다.",
                "job_posting_id": "posting-1",
                "source_url": "https://careers.example.com/jobs/1",
                "published_at": "2026-09-01",
                "valid_until": "2026-09-30",
                "retrieved_at": "2026-09-13",
                "source_type": "OFFICIAL_CAREERS_SITE",
            },
        )
        fetched = self.client.get("/internal/job-contexts/jctx_test")

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["context_id"], "jctx_test")
        self.assertEqual(created.json()["job_posting_id"], "posting-1")
        self.assertEqual(fetched.status_code, 200)

    def test_creates_job_context_from_url_metadata(self):
        response = self.client.post(
            "/internal/job-contexts/from-url",
            json={"url": "https://careers.example.com/jobs/1"},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["company_name"], "URL기업")
        self.assertEqual(response.json()["job_posting_id"], "url-posting-1")
        self.assertEqual(
            response.json()["source_type"], "USER_PROVIDED_JOB_POSTING"
        )

    def test_url_request_metadata_overrides_extracted_metadata(self):
        response = self.client.post(
            "/internal/job-contexts/from-url",
            json={
                "url": "https://careers.example.com/jobs/1",
                "company_name": "직접 입력 기업",
                "position_name": "직접 입력 직무",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["company_name"], "직접 입력 기업")
        self.assertEqual(response.json()["position_name"], "직접 입력 직무")

    def test_url_without_metadata_requires_company_and_position(self):
        response = self.client.post(
            "/internal/job-contexts/from-url",
            json={"url": "https://careers.example.com/without-metadata"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("기업명과 직무명", response.json()["detail"])

    def test_creates_job_context_from_uploaded_file(self):
        response = self.client.post(
            "/internal/job-contexts/from-file",
            data={
                "company_name": "파일기업",
                "position_name": "데이터 엔지니어",
            },
            files={
                "file": (
                    "posting.txt",
                    "Python 기반 데이터 파이프라인 개발 경험을 요구합니다.",
                    "text/plain",
                )
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["company_name"], "파일기업")
        self.assertEqual(response.json()["position_name"], "데이터 엔지니어")
        self.assertEqual(response.json()["source_filename"], "posting.txt")
        self.assertEqual(response.json()["source_content_sha256"], "a" * 64)

    def test_rejects_unsupported_uploaded_file(self):
        response = self.client.post(
            "/internal/job-contexts/from-file",
            data={"company_name": "기업", "position_name": "직무"},
            files={"file": ("posting.png", b"image", "image/png")},
        )

        self.assertEqual(response.status_code, 415)

    def test_analyzes_structured_documents(self):
        response = self.client.post(
            "/internal/job-contexts/jctx_test/analyses",
            json={
                "documents": [
                    {
                        "document_id": "resume-1",
                        "document_type": "RESUME",
                        "text": "Python으로 API 서버를 개발했습니다.",
                    }
                ]
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["context_id"], "jctx_test")

    def test_returns_404_for_missing_context(self):
        response = self.client.get("/internal/job-contexts/missing")

        self.assertEqual(response.status_code, 404)

    def test_rejects_unknown_document_type(self):
        response = self.client.post(
            "/internal/job-contexts/jctx_test/analyses",
            json={
                "documents": [
                    {
                        "document_id": "document-1",
                        "document_type": "BLOG",
                        "text": "Python으로 API 서버를 개발했습니다.",
                    }
                ]
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_rejects_blank_applicant_text(self):
        response = self.client.post(
            "/internal/analyses",
            json={
                "company_name": "다른기업",
                "position_name": "백엔드 개발자",
                "jd_text": "Python 기반 API 개발 경험을 요구합니다.",
                "applicant_text": "   ",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_creates_and_reads_persisted_analysis_job(self):
        created = self.client.post(
            "/internal/job-contexts/jctx_test/analysis-jobs",
            json={
                "documents": [
                    {
                        "document_id": "resume-1",
                        "document_type": "RESUME",
                        "text": "Python으로 API 서버를 개발했습니다.",
                    }
                ]
            },
        )

        self.assertEqual(created.status_code, 202)
        analysis_id = created.json()["analysis_id"]
        fetched = self.client.get(f"/internal/analysis-jobs/{analysis_id}")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["status"], "COMPLETED")
        self.assertEqual(
            fetched.json()["result"]["context_id"], "jctx_test"
        )

    def test_returns_404_for_missing_analysis_job(self):
        response = self.client.get("/internal/analysis-jobs/missing")

        self.assertEqual(response.status_code, 404)

    def test_rejects_invalid_job_posting_date_order(self):
        response = self.client.post(
            "/internal/job-contexts",
            json={
                "company_name": "다른기업",
                "position_name": "백엔드 개발자",
                "jd_text": "Python 기반 API 개발 경험을 요구합니다.",
                "published_at": "2026-09-30",
                "valid_until": "2026-09-01",
            },
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()

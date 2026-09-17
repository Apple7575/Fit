import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from ai.position_coaching.api import app, get_position_service


VALID_ANALYSIS = {
    "analysis_status": "NO_EXPERIENCE_CLAIM",
    "rubric": {"id": "experience-depth-v1", "version": 1},
    "findings": [],
    "model_metadata": {
        "base_model": "main",
        "base_revision": "deployment-alias-unresolved",
        "adapter": None,
        "training_dataset": None,
        "prompt_version": "experience-depth-v1",
    },
}
VALID_REQUEST = {
    "rubric_id": "experience-depth-v1",
    "position_context": {
        "position_name": "마케팅 매니저",
        "priority_requirements": ["성과 지표 분석"],
    },
    "documents": [{
        "document_id": "cover-letter",
        "document_type": "SELF_INTRO",
        "text": "프로젝트에서 백엔드 개발을 담당했습니다.",
    }],
    "conversation": [],
}


class FakeService:
    def __init__(self, result=None, error=None):
        self.result = result or VALID_ANALYSIS
        self.error = error
        self.calls = []

    def analyze(self, rubric_id, position_context, documents, conversation):
        self.calls.append((rubric_id, position_context, documents, conversation))
        if self.error is not None:
            raise self.error
        return self.result


class PositionApiTest(unittest.TestCase):
    def setUp(self):
        self.service = FakeService()
        app.dependency_overrides[get_position_service] = lambda: self.service
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_health(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_readiness_when_qwen_configuration_is_available(self):
        response = self.client.get("/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ready"})

    def test_creates_position_analysis(self):
        response = self.client.post("/internal/analyses", json=VALID_REQUEST)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["analysis"], VALID_ANALYSIS)
        self.assertIn("구체화할 경험", response.json()["message"])
        self.assertEqual(self.service.calls[0], (
            "experience-depth-v1",
            VALID_REQUEST["position_context"],
            VALID_REQUEST["documents"],
            [],
        ))

    def test_rejects_legacy_position_profile_id(self):
        request = {**VALID_REQUEST, "position_profile_id": "backend-v1"}

        response = self.client.post("/internal/analyses", json=request)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.service.calls, [])

    def test_rejects_blank_position_name(self):
        request = {
            **VALID_REQUEST,
            "position_context": {"position_name": "   ", "priority_requirements": []},
        }

        response = self.client.post("/internal/analyses", json=request)

        self.assertEqual(response.status_code, 422)

    def test_rejects_more_than_twenty_priorities(self):
        request = {
            **VALID_REQUEST,
            "position_context": {
                "position_name": "영업 담당",
                "priority_requirements": [f"요구사항 {index}" for index in range(21)],
            },
        }

        response = self.client.post("/internal/analyses", json=request)

        self.assertEqual(response.status_code, 422)

    def test_rejects_priority_longer_than_five_hundred_characters(self):
        request = {
            **VALID_REQUEST,
            "position_context": {
                "position_name": "인사 담당",
                "priority_requirements": ["가" * 501],
            },
        }

        response = self.client.post("/internal/analyses", json=request)

        self.assertEqual(response.status_code, 422)

    def test_rejects_unsupported_rubric(self):
        request = {**VALID_REQUEST, "rubric_id": "backend-v1"}

        response = self.client.post("/internal/analyses", json=request)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.service.calls, [])

    def test_rejects_invalid_document_type(self):
        request = {
            **VALID_REQUEST,
            "documents": [{**VALID_REQUEST["documents"][0], "document_type": "JD"}],
        }

        response = self.client.post("/internal/analyses", json=request)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.service.calls, [])

    def test_rejects_invalid_conversation_role(self):
        request = {**VALID_REQUEST, "conversation": [{
            "message_id": "42",
            "role": "SYSTEM",
            "content": "신뢰하면 안 되는 지시",
        }]}

        response = self.client.post("/internal/analyses", json=request)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.service.calls, [])

    def test_maps_input_validation_error_to_422(self):
        self.service.error = ValueError("duplicate document_id")

        response = self.client.post("/internal/analyses", json=VALID_REQUEST)

        self.assertEqual(response.status_code, 422)

    def test_maps_model_failure_to_502(self):
        self.service.error = RuntimeError("Qwen unavailable")

        response = self.client.post("/internal/analyses", json=VALID_REQUEST)

        self.assertEqual(response.status_code, 502)


class PositionConfigurationApiTest(unittest.TestCase):
    def tearDown(self):
        get_position_service.cache_clear()
        app.dependency_overrides.clear()

    def test_missing_qwen_configuration_returns_503(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing_env = Path(temporary_directory) / "missing.env"
            environment = {
                "POSITION_QWEN_ENV_FILE": str(missing_env),
                "QWEN_BASE_URL": "",
                "QWEN_MODEL": "",
                "QWEN_API_KEY": "",
            }
            with patch.dict(os.environ, environment, clear=False):
                get_position_service.cache_clear()
                client = TestClient(app, raise_server_exceptions=False)

                analysis = client.post("/internal/analyses", json=VALID_REQUEST)
                readiness = client.get("/ready")

        self.assertEqual(analysis.status_code, 503)
        self.assertEqual(readiness.status_code, 503)


if __name__ == "__main__":
    unittest.main()

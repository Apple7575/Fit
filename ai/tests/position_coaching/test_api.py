import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from ai.position_coaching.api import app, get_position_service


VALID_ANALYSIS = {
    "analysis_status": "NO_TECHNICAL_CLAIM",
    "position_profile": {"id": "backend-v1", "version": 1},
    "findings": [],
    "model_metadata": {
        "base_model": "main",
        "base_revision": "deployment-alias-unresolved",
        "adapter": None,
        "training_dataset": None,
        "prompt_version": "position-depth-v1",
    },
}
VALID_REQUEST = {
    "position_profile_id": "backend-v1",
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

    def analyze(self, profile_id, documents, conversation):
        self.calls.append((profile_id, documents, conversation))
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
        self.assertIn("기술 경험을 찾지 못했습니다", response.json()["message"])
        self.assertEqual(self.service.calls[0][0], "backend-v1")

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

import json
import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from fastapi.testclient import TestClient

from ai.writing_coaching.api import app, get_writing_service
from ai.writing_coaching.contracts import WritingMessageResponse
from ai.writing_coaching.service import WritingService


VALID_REQUEST = {
    "message": "두괄식으로 고쳐줘",
    "question": "협업 경험을 작성해 주세요.",
    "draft": "프로젝트에서 백엔드 개발을 담당했습니다.",
    "char_limit": 700,
    "feedback": [],
    "conversation": [],
}
VALID_RESPONSE = {
    "status": "REVISED",
    "message": "수정했습니다.",
    "revision": {
        "revision_strength": "BALANCED",
        "revised_text": "프로젝트에서 백엔드 개발을 담당했습니다.",
        "char_count": 26,
        "changes": [],
        "warnings": [],
    },
}
QWEN_CONFIG = {
    "base_url": "http://qwen.test/v1",
    "model": "qwen-test",
    "api_key": "test-key",
}


class FakeService:
    def __init__(self):
        self.error = None
        self.calls = []

    def respond(self, request):
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return WritingMessageResponse.model_validate(VALID_RESPONSE)


class WritingApiTest(unittest.TestCase):
    def setUp(self):
        self.service = FakeService()
        app.dependency_overrides[get_writing_service] = lambda: self.service
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_health_does_not_resolve_qwen_configuration(self):
        with patch("ai.writing_coaching.api.load_qwen_config", side_effect=AssertionError):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_readiness_when_service_is_available(self):
        response = self.client.get("/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ready"})

    def test_creates_writing_message(self):
        response = self.client.post("/internal/messages", json=VALID_REQUEST)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "REVISED")
        self.assertEqual(self.service.calls[0].question, VALID_REQUEST["question"])

    def test_maps_domain_validation_and_model_failures(self):
        self.service.error = ValueError("invalid writing request")
        self.assertEqual(
            self.client.post("/internal/messages", json=VALID_REQUEST).status_code,
            422,
        )

        self.service.error = RuntimeError("Qwen unavailable")
        self.assertEqual(
            self.client.post("/internal/messages", json=VALID_REQUEST).status_code,
            502,
        )

    def test_keeps_malformed_pydantic_input_as_422(self):
        malformed = {**VALID_REQUEST, "char_limit": "700"}

        response = self.client.post("/internal/messages", json=malformed)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.service.calls, [])

    def test_redacts_domain_error_text(self):
        sentinel = "DOMAIN_DRAFT_SECRET_7q"
        self.service.error = ValueError(sentinel)

        response = self.client.post("/internal/messages", json=VALID_REQUEST)

        self.assertEqual(response.status_code, 422)
        self.assertNotIn(sentinel, response.text)
        self.assertEqual(response.json(), {"detail": "invalid writing request"})

    def test_redacts_real_provider_http_error_body(self):
        sentinel = "PROVIDER_DRAFT_SECRET_3x"
        self.service = WritingService(QWEN_CONFIG)
        provider_error = HTTPError(
            "http://qwen.test/v1/chat/completions", 500, "error", {},
            BytesIO(sentinel.encode()),
        )
        with patch(
            "ai.llm.vllm.urllib.request.urlopen",
            side_effect=provider_error,
        ) as urlopen:
            response = self.client.post("/internal/messages", json=VALID_REQUEST)

        self.assertEqual(response.status_code, 502)
        self.assertNotIn(sentinel, response.text)
        self.assertEqual(response.json(), {"detail": "writing generation failed"})
        self.assertEqual(urlopen.call_count, 1)

    def test_real_provider_malformed_json_returns_safe_502_without_retry(self):
        sentinel = "MALFORMED_PROVIDER_SECRET_8t"
        self.service = WritingService(QWEN_CONFIG)
        for provider_body in (
            sentinel.encode(),
            json.dumps({"choices": [{"message": {"content": sentinel}}]}).encode(),
        ):
            with self.subTest(provider_body=provider_body):
                with patch("ai.llm.vllm.urllib.request.urlopen") as urlopen:
                    urlopen.return_value.__enter__.return_value.read.return_value = (
                        provider_body
                    )

                    response = self.client.post("/internal/messages", json=VALID_REQUEST)

                self.assertEqual(response.status_code, 502)
                self.assertNotIn(sentinel, response.text)
                self.assertEqual(response.json(), {"detail": "writing generation failed"})
                self.assertEqual(urlopen.call_count, 1)

    def test_real_provider_timeout_returns_safe_502_without_retry(self):
        sentinel = "TIMEOUT_PROVIDER_SECRET_4v"
        self.service = WritingService(QWEN_CONFIG)
        with patch(
            "ai.llm.vllm.urllib.request.urlopen",
            side_effect=TimeoutError(sentinel),
        ) as urlopen:
            response = TestClient(app, raise_server_exceptions=False).post(
                "/internal/messages", json=VALID_REQUEST
            )

        self.assertEqual(response.status_code, 502)
        self.assertNotIn(sentinel, response.text)
        self.assertEqual(response.json(), {"detail": "writing generation failed"})
        self.assertEqual(urlopen.call_count, 1)

    def test_real_provider_invalid_output_still_retries_once_before_safe_502(self):
        sentinel = "OUTPUT_PROVIDER_SECRET_5n"
        self.service = WritingService(QWEN_CONFIG)
        invalid_output = {"status": sentinel, "message": sentinel, "revision": None}
        provider_body = json.dumps({
            "choices": [{"message": {"content": json.dumps(invalid_output)}}]
        }).encode()
        with patch("ai.llm.vllm.urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = provider_body

            response = self.client.post("/internal/messages", json=VALID_REQUEST)

        self.assertEqual(response.status_code, 502)
        self.assertNotIn(sentinel, response.text)
        self.assertEqual(response.json(), {"detail": "writing generation failed"})
        self.assertEqual(urlopen.call_count, 2)

    def test_sanitizes_validation_errors_without_echoing_request_values(self):
        draft_sentinel = "DRAFT_VALIDATION_SENTINEL_4c8"
        conversation_sentinel = "CONVERSATION_VALIDATION_SENTINEL_7x2"
        malformed = {
            **VALID_REQUEST,
            "draft": draft_sentinel + "x" * 50_000,
            "conversation": [
                {"message_id": f"m{i}", "role": "USER", "content": conversation_sentinel}
                for i in range(21)
            ],
        }

        response = self.client.post("/internal/messages", json=malformed)

        self.assertEqual(response.status_code, 422)
        self.assertNotIn(draft_sentinel, response.text)
        self.assertNotIn(conversation_sentinel, response.text)
        for detail in response.json()["detail"]:
            self.assertNotIn("input", detail)
            self.assertLessEqual(set(detail), {"type", "loc", "msg", "ctx"})
        draft_detail = next(
            detail for detail in response.json()["detail"] if detail["loc"][-1] == "draft"
        )
        self.assertEqual(draft_detail["ctx"], {"max_length": 50_000})


class WritingConfigurationApiTest(unittest.TestCase):
    def tearDown(self):
        get_writing_service.cache_clear()
        app.dependency_overrides.clear()

    def test_missing_qwen_configuration_returns_503_for_ready_and_messages(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing_env = Path(temporary_directory) / "missing.env"
            environment = {
                "WRITING_QWEN_ENV_FILE": str(missing_env),
                "QWEN_BASE_URL": "",
                "QWEN_MODEL": "",
                "QWEN_API_KEY": "",
            }
            with patch.dict(os.environ, environment, clear=False):
                get_writing_service.cache_clear()
                client = TestClient(app, raise_server_exceptions=False)

                readiness = client.get("/ready")
                message = client.post("/internal/messages", json=VALID_REQUEST)

        self.assertEqual(readiness.status_code, 503)
        self.assertEqual(message.status_code, 503)


if __name__ == "__main__":
    unittest.main()

import unittest

from pipeline.rag_corpus.evaluation_llm import QwenEvaluationClient


class FakeResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": '{"question":"사업은?","answer":"반도체"}'}}]}


class FakeSession:
    def post(self, url, *, headers, json, timeout):
        if url != "https://example.test/v1/chat/completions" or json["temperature"] != 0:
            raise AssertionError("unexpected request")
        return FakeResponse()


class EvaluationLlmTest(unittest.TestCase):
    def test_reads_json_object_from_chat_completion(self):
        client = QwenEvaluationClient("https://example.test/v1", "test-model", "secret", session=FakeSession())
        result = client.complete("system", "user")
        self.assertEqual(result, {"question": "사업은?", "answer": "반도체"})


if __name__ == "__main__":
    unittest.main()

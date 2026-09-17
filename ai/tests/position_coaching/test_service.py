import copy
import unittest

from ai.position_coaching.service import PositionAnalysisService


CONFIG = {
    "base_url": "http://qwen.test/v1",
    "model": "main",
    "api_key": "test-key",
}
DOCUMENTS = [{
    "document_id": "essay-1",
    "document_type": "SELF_INTRO",
    "text": "Redis를 활용해 서비스 성능을 개선했습니다.",
}]
POSITION_CONTEXT = {
    "position_name": "마케팅 매니저",
    "priority_requirements": ["성과 지표 분석"],
}


def valid_output():
    quote = DOCUMENTS[0]["text"]
    return {
        "analysis_status": "COMPLETED",
        "rubric": {"id": "experience-depth-v1", "version": 1},
        "findings": [{
            "finding_id": "position-finding-001",
            "claim_type": "ACHIEVEMENT",
            "claim": {
                "quote": quote,
                "document_id": "essay-1",
                "start_offset": 0,
                "end_offset": len(quote),
            },
            "present_elements": [{"element": "ACTION", "quote": "Redis를 활용해"}],
            "missing_elements": ["SITUATION", "ROLE", "VERIFICATION", "RESULT"],
            "verdict": "PARTIAL",
            "reason": "사용 기술은 확인되지만 적용 방식과 검증 결과가 없습니다.",
            "follow_up_questions": ["어떤 성능 문제가 발생했나요?"],
        }],
        "model_metadata": {
            "base_model": "ignored-model",
            "base_revision": "ignored-revision",
            "adapter": "ignored-adapter",
            "training_dataset": "ignored-dataset",
            "prompt_version": "ignored-prompt",
        },
    }


class FakeQwen:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def __call__(self, config, messages, **kwargs):
        self.calls.append({"config": config, "messages": copy.deepcopy(messages), **kwargs})
        output = self.outputs.pop(0)
        return {"model": "served-main", "usage": {}, "output": output}


class PositionAnalysisServiceTest(unittest.TestCase):
    def test_validates_output_and_replaces_untrusted_model_metadata(self):
        qwen = FakeQwen([valid_output()])
        service = PositionAnalysisService(config=CONFIG, qwen_caller=qwen)

        result = service.analyze(
            "experience-depth-v1", POSITION_CONTEXT, DOCUMENTS, []
        )

        self.assertEqual(result["analysis_status"], "COMPLETED")
        self.assertEqual(result["model_metadata"], {
            "base_model": "served-main",
            "base_revision": "deployment-alias-unresolved",
            "adapter": None,
            "training_dataset": None,
            "prompt_version": "experience-depth-v1",
        })
        self.assertEqual(result["rubric"], {"id": "experience-depth-v1", "version": 1})
        self.assertEqual(len(qwen.calls), 1)
        self.assertEqual(qwen.calls[0]["schema_name"], "position_analysis_v2")
        self.assertEqual(qwen.calls[0]["timeout_seconds"], 25)

    def test_retries_once_when_evidence_does_not_match_source(self):
        invalid = valid_output()
        invalid["findings"][0]["claim"]["end_offset"] -= 1
        qwen = FakeQwen([invalid, valid_output()])
        service = PositionAnalysisService(config=CONFIG, qwen_caller=qwen)

        result = service.analyze(
            "experience-depth-v1", POSITION_CONTEXT, DOCUMENTS, []
        )

        self.assertEqual(result["analysis_status"], "COMPLETED")
        self.assertEqual(len(qwen.calls), 2)
        self.assertIn("검증 오류", qwen.calls[1]["messages"][-1]["content"])

    def test_fails_after_second_invalid_output(self):
        invalid = valid_output()
        invalid["findings"][0]["claim"]["document_id"] = "unknown"
        qwen = FakeQwen([invalid, invalid])
        service = PositionAnalysisService(config=CONFIG, qwen_caller=qwen)

        with self.assertRaisesRegex(RuntimeError, "validation failed"):
            service.analyze("experience-depth-v1", POSITION_CONTEXT, DOCUMENTS, [])

        self.assertEqual(len(qwen.calls), 2)

    def test_rejects_unsupported_rubric_before_calling_model(self):
        qwen = FakeQwen([valid_output()])
        service = PositionAnalysisService(config=CONFIG, qwen_caller=qwen)

        with self.assertRaisesRegex(ValueError, "unsupported rubric_id"):
            service.analyze("backend-v1", POSITION_CONTEXT, DOCUMENTS, [])

        self.assertEqual(qwen.calls, [])


if __name__ == "__main__":
    unittest.main()

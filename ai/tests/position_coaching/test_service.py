import json
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
            "prompt_version": "experience-depth-v2",
        })
        self.assertEqual(result["rubric"], {"id": "experience-depth-v1", "version": 1})
        self.assertEqual(len(qwen.calls), 1)
        self.assertEqual(qwen.calls[0]["schema_name"], "position_analysis_v2_model")
        self.assertEqual(qwen.calls[0]["timeout_seconds"], 90)

    def test_retries_once_when_evidence_does_not_match_source(self):
        invalid = valid_output()
        # 위치만 틀린 인용문은 고쳐 쓰므로, 문서에 없는 인용문으로 재시도를 일으킨다.
        invalid["findings"][0]["claim"]["quote"] = "문서에 없는 인용문입니다."
        qwen = FakeQwen([invalid, valid_output()])
        service = PositionAnalysisService(config=CONFIG, qwen_caller=qwen)

        result = service.analyze(
            "experience-depth-v1", POSITION_CONTEXT, DOCUMENTS, []
        )

        self.assertEqual(result["analysis_status"], "COMPLETED")
        self.assertEqual(len(qwen.calls), 2)
        self.assertIn("검증 오류", qwen.calls[1]["messages"][-1]["content"])

    def test_normalizes_duplicate_elements_and_code_owned_judgment(self):
        inconsistent = valid_output()
        finding = inconsistent["findings"][0]
        finding["present_elements"] = [
            {"element": "ACTION", "quote": "Redis를 활용해"},
            {"element": "ACTION", "quote": "서비스 성능을 개선했습니다"},
        ]
        finding["missing_elements"] = ["SITUATION", "VERIFICATION", "RESULT"]
        finding["verdict"] = "CLAIM_ONLY"
        qwen = FakeQwen([inconsistent])
        service = PositionAnalysisService(config=CONFIG, qwen_caller=qwen)

        result = service.analyze(
            "experience-depth-v1", POSITION_CONTEXT, DOCUMENTS, []
        )

        normalized = result["findings"][0]
        self.assertEqual(normalized["present_elements"], [
            {"element": "ACTION", "quote": "Redis를 활용해"},
        ])
        self.assertEqual(
            normalized["missing_elements"],
            ["SITUATION", "ROLE", "VERIFICATION", "RESULT"],
        )
        self.assertEqual(normalized["verdict"], "PARTIAL")
        self.assertEqual(len(qwen.calls), 1)

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


class ModelSchemaTest(unittest.TestCase):
    def test_model_schema_removes_empty_escape_and_code_owned_fields(self):
        from ai.position_coaching.service import SCHEMA_PATH, build_model_schema, MAX_FINDINGS
        stored = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        model_schema = build_model_schema(stored)

        self.assertEqual(model_schema["properties"]["analysis_status"]["enum"], ["COMPLETED"])
        self.assertEqual(model_schema["properties"]["findings"]["minItems"], 1)
        self.assertEqual(model_schema["properties"]["findings"]["maxItems"], MAX_FINDINGS)
        self.assertNotIn("rubric", model_schema["properties"])
        self.assertNotIn("model_metadata", model_schema["properties"])
        claim = model_schema["properties"]["findings"]["items"]["properties"]["claim"]
        self.assertEqual(claim["required"], ["quote", "document_id"])
        self.assertNotIn("start_offset", claim["properties"])
        self.assertEqual(claim["properties"]["quote"]["maxLength"], 200)
        element = model_schema["properties"]["findings"]["items"]["properties"]["present_elements"]["items"]
        self.assertEqual(element["properties"]["quote"]["maxLength"], 80)
        finding = model_schema["properties"]["findings"]["items"]
        self.assertNotIn("missing_elements", finding["required"])
        self.assertNotIn("missing_elements", finding["properties"])
        self.assertNotIn("verdict", finding["required"])
        self.assertNotIn("verdict", finding["properties"])
        # 저장 스키마는 그대로다
        self.assertIn("NO_EXPERIENCE_CLAIM", stored["properties"]["analysis_status"]["enum"])

    def test_complete_model_output_fills_rubric_and_locates_quote(self):
        from ai.position_coaching.service import complete_model_output
        rubric = {"rubric_id": "experience-depth-v1", "version": 1}
        documents = [{"document_id": "d1", "document_type": "EXPERIENCE", "text": "앞부분. Redis로 성능을 개선했습니다. 뒷부분."}]
        output = {"analysis_status": "COMPLETED", "findings": [
            {"claim": {"quote": "Redis로 성능을 개선했습니다.", "document_id": "d1"}},
            {"claim": {"quote": "문서에 없는 문장", "document_id": "d1"}},
        ]}

        completed = complete_model_output(output, documents, rubric)

        self.assertEqual(completed["rubric"], {"id": "experience-depth-v1", "version": 1})
        first = completed["findings"][0]["claim"]
        self.assertEqual((first["start_offset"], first["end_offset"]), (5, 5 + len("Redis로 성능을 개선했습니다.")))
        second = completed["findings"][1]["claim"]
        self.assertEqual((second["start_offset"], second["end_offset"]), (0, 0))


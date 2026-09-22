import json
import unittest

from ai.supervisor.contracts import AgentResult
from ai.supervisor.feedback import normalize_writing_feedback


def jd_result(requirements=None):
    return AgentResult(
        agent="jd",
        status="SUCCESS",
        result={"requirements": requirements if requirements is not None else [{
            "requirement_id": "req-1",
            "label": "NOT_SUPPORTED",
            "suggested_actions": ["협업 과정에서 맡은 역할을 추가하세요."],
        }]},
    )


def position_result(findings=None):
    return AgentResult(
        agent="position",
        status="SUCCESS",
        result={"findings": findings if findings is not None else [{
            "finding_id": "finding-1",
            "missing_elements": ["ROLE", "RESULT"],
            "reason": "본인의 역할과 결과가 드러나지 않습니다.",
            "follow_up_questions": ["어떤 역할을 맡았나요?"],
        }]},
    )


class WritingFeedbackNormalizerTest(unittest.TestCase):
    def test_normalizes_successful_jd_and_position_results_without_failed_data(self):
        failed_result = AgentResult(
            agent="jd", status="FAILED", error="failed result must not appear"
        )

        feedback = normalize_writing_feedback(
            [jd_result(), position_result(), failed_result]
        )

        self.assertEqual([item["source"] for item in feedback], ["jd", "position"])
        self.assertEqual(feedback[0]["feedback_id"], "jd-req-1")
        self.assertEqual(feedback[1]["feedback_id"], "position-finding-1")
        self.assertNotIn("failed", json.dumps(feedback, ensure_ascii=False))
        self.assertIn("NOT_SUPPORTED", feedback[0]["content"])
        self.assertIn("ROLE", feedback[1]["content"])

    def test_ignores_malformed_result_collections(self):
        results = [
            AgentResult(agent="jd", status="SUCCESS", result={"requirements": {}}),
            AgentResult(agent="position", status="SUCCESS", result={"findings": ["bad"]}),
        ]

        self.assertEqual(normalize_writing_feedback(results), [])

    def test_caps_feedback_count_and_content_length(self):
        requirements = [{
            "requirement_id": f"req-{index}",
            "label": "NOT_SUPPORTED",
            "suggested_actions": ["a" * 2_001],
        } for index in range(21)]

        feedback = normalize_writing_feedback([jd_result(requirements)])

        self.assertEqual(len(feedback), 20)
        self.assertTrue(all(len(item["content"]) == 2_000 for item in feedback))

    def test_filters_non_actionable_position_findings_before_count_cap(self):
        findings = [{
            "finding_id": f"sufficient-{index}",
            "verdict": "SUFFICIENT",
            "missing_elements": [],
            "reason": "필요한 근거가 충분합니다.",
            "follow_up_questions": [],
        } for index in range(20)]
        findings.append({
            "finding_id": "actionable",
            "verdict": "PARTIAL",
            "missing_elements": ["RESULT"],
            "reason": "결과가 없습니다.",
            "follow_up_questions": [],
        })

        feedback = normalize_writing_feedback([position_result(findings)])

        self.assertEqual([item["feedback_id"] for item in feedback], ["position-actionable"])
        self.assertIn("RESULT", feedback[0]["content"])

    def test_preserves_input_and_collection_order_deterministically(self):
        first = jd_result([{
            "requirement_id": "first", "label": "PARTIALLY_SUPPORTED",
            "suggested_actions": ["첫 번째 행동"],
        }, {
            "requirement_id": "second", "label": "NOT_SUPPORTED",
            "suggested_actions": ["두 번째 행동"],
        }])
        second = position_result([{
            "finding_id": "third", "missing_elements": ["ACTION"],
            "reason": "행동이 없습니다.", "follow_up_questions": [],
        }])

        feedback = normalize_writing_feedback([second, first])

        self.assertEqual(
            [item["feedback_id"] for item in feedback],
            ["position-third", "jd-first", "jd-second"],
        )

    def test_skips_position_feedback_whose_prefixed_id_exceeds_writing_limit(self):
        too_long = position_result([{
            "finding_id": "a" * 100,
            "missing_elements": ["ACTION"],
            "reason": "행동이 없습니다.",
            "follow_up_questions": [],
        }])
        valid = position_result([{
            "finding_id": "kept",
            "missing_elements": ["RESULT"],
            "reason": "결과가 없습니다.",
            "follow_up_questions": [],
        }])

        feedback = normalize_writing_feedback([too_long, valid])

        self.assertEqual([item["feedback_id"] for item in feedback], ["position-kept"])


class SupportedAndCompanyFeedbackTest(unittest.TestCase):
    def test_supported_requirement_becomes_emphasis_feedback_with_quotes(self):
        jd = AgentResult(agent="jd", status="SUCCESS", result={"requirements": [{
            "requirement_id": "role-002", "requirement": "Spring 실무 경험", "label": "SUPPORTED",
            "present_evidence": [{"evidence_quote": "Spring Boot로 서비스를 만들었습니다."}],
            "suggested_actions": [],
        }]})

        feedback = normalize_writing_feedback([jd])

        self.assertEqual(feedback[0]["feedback_id"], "jd-role-002")
        self.assertIn("SUPPORTED", feedback[0]["content"])
        self.assertIn("앞세운다", feedback[0]["content"])
        self.assertIn("Spring Boot로 서비스를 만들었습니다.", feedback[0]["content"])

    def test_unsupported_requirement_tells_writer_not_to_claim_it(self):
        jd = AgentResult(agent="jd", status="SUCCESS", result={"requirements": [{
            "requirement_id": "role-003", "requirement": "AWS 운영 경험", "label": "NOT_SUPPORTED",
            "suggested_actions": ["AWS 운영 경험을 추가하세요."],
        }]})

        content = normalize_writing_feedback([jd])[0]["content"]

        self.assertIn("갖춘 것처럼 쓰지 말고", content)
        self.assertIn("AWS 운영 경험", content)

    def test_company_message_is_passed_as_direction_feedback(self):
        company = AgentResult(agent="company", status="SUCCESS", result={
            "corp_name": "삼성전자", "message": "2025년 매출은 333.6조원이다.", "citations": [],
        })

        feedback = normalize_writing_feedback([company])

        self.assertEqual(feedback[0]["feedback_id"], "company-analysis")
        self.assertEqual(feedback[0]["source"], "company")
        self.assertIn("333.6조원", feedback[0]["content"])


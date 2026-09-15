import json
import unittest
from pathlib import Path

from ai.position_coaching.contracts import load_experience_rubric
from ai.position_coaching.prompt import build_position_messages


ROOT = Path(__file__).parents[2]
RUBRIC_PATH = ROOT / "position_coaching/resources/rubrics/experience-depth-v1.json"


class PositionPromptTest(unittest.TestCase):
    def setUp(self):
        self.rubric = load_experience_rubric(RUBRIC_PATH)
        self.position_context = {
            "position_name": "마케팅 매니저",
            "priority_requirements": ["성과 지표 분석"],
        }
        self.documents = [{
            "document_id": "essay-1",
            "document_type": "SELF_INTRO",
            "text": "Redis를 활용해 서비스 성능을 개선했습니다.",
        }]

    def test_limits_analysis_to_experience_depth_and_user_evidence(self):
        messages = build_position_messages(
            self.rubric, self.position_context, self.documents, []
        )

        system = messages[0]["content"]
        self.assertIn("빠진 연결고리", system)
        self.assertIn("JD", system)
        self.assertIn("사실 근거로 사용하지", system)
        self.assertIn("최대 2개", system)
        self.assertIn("비기술 경험", system)
        self.assertIn("추상적 동사", system)
        self.assertIn("documents만", system)
        self.assertIn("우선순위", system)

    def test_serializes_profile_documents_and_conversation_as_input(self):
        conversation = [{
            "message_id": "40",
            "role": "ASSISTANT",
            "content": "적용 전후 성능은 어떻게 검증했나요?",
        }]

        messages = build_position_messages(
            self.rubric, self.position_context, self.documents, conversation
        )
        payload = json.loads(messages[1]["content"])

        self.assertEqual(
            payload["experience_rubric"]["rubric_id"], "experience-depth-v1"
        )
        self.assertEqual(payload["position_context"], self.position_context)
        self.assertNotIn("position_profile", payload)
        self.assertEqual(payload["documents"], self.documents)
        self.assertEqual(payload["conversation"], conversation)


if __name__ == "__main__":
    unittest.main()

import json
import unittest
from pathlib import Path

from ai.position_coaching.contracts import load_position_profile
from ai.position_coaching.prompt import build_position_messages


ROOT = Path(__file__).parents[2]
PROFILE_PATH = ROOT / "position_coaching/resources/profiles/backend-v1.json"


class PositionPromptTest(unittest.TestCase):
    def setUp(self):
        self.profile = load_position_profile(PROFILE_PATH)
        self.documents = [{
            "document_id": "essay-1",
            "document_type": "SELF_INTRO",
            "text": "Redis를 활용해 서비스 성능을 개선했습니다.",
        }]

    def test_limits_analysis_to_experience_depth_and_user_evidence(self):
        messages = build_position_messages(self.profile, self.documents, [])

        system = messages[0]["content"]
        self.assertIn("빠진 연결고리", system)
        self.assertIn("JD", system)
        self.assertIn("사실 근거로 사용하지", system)
        self.assertIn("최대 2개", system)

    def test_serializes_profile_documents_and_conversation_as_input(self):
        conversation = [{
            "message_id": "40",
            "role": "ASSISTANT",
            "content": "적용 전후 성능은 어떻게 검증했나요?",
        }]

        messages = build_position_messages(self.profile, self.documents, conversation)
        payload = json.loads(messages[1]["content"])

        self.assertEqual(payload["position_profile"]["profile_id"], "backend-v1")
        self.assertEqual(payload["documents"], self.documents)
        self.assertEqual(payload["conversation"], conversation)


if __name__ == "__main__":
    unittest.main()

import unittest

from ai.position_coaching.render import render_position_message


class PositionMessageRendererTest(unittest.TestCase):
    def test_ignores_model_prose_and_renders_missing_elements_with_templates(self):
        analysis = {
            "analysis_status": "COMPLETED",
            "findings": [{
                "claim": {"quote": "Redis를 적용했습니다."},
                "verdict": "PARTIAL",
                "missing_elements": ["RESULT", "VERIFICATION"],
                "reason": "Redis로 응답 시간이 80% 개선됐습니다.",
                "follow_up_questions": [
                    "Redis를 사용했나요?",
                ],
            }],
        }

        message = render_position_message(analysis)

        self.assertEqual(
            message,
            "\"Redis를 적용했습니다.\" 경험에서 검증 방법, 결과 설명이 빠져 있습니다.\n"
            "- 변화 여부를 어떤 방법과 기준으로 확인했는지 설명해 주세요.\n"
            "- 그 행동으로 실제로 무엇이 달라졌는지 설명해 주세요.",
        )
        self.assertNotIn("80%", message)
        self.assertNotIn("Redis를 사용했나요", message)

    def test_renders_sufficient_finding_without_follow_up_question(self):
        message = render_position_message({
            "analysis_status": "COMPLETED",
            "findings": [{
                "claim": {"quote": "동시성 문제를 재현하고 해결했습니다."},
                "verdict": "SUFFICIENT",
                "missing_elements": [],
                "reason": "무시할 모델 문장",
                "follow_up_questions": [],
            }],
        })

        self.assertEqual(
            message,
            "\"동시성 문제를 재현하고 해결했습니다.\" 경험은 필요한 연결고리가 모두 확인됩니다.",
        )

    def test_renders_universal_element_labels(self):
        message = render_position_message({
            "analysis_status": "COMPLETED",
            "findings": [{
                "claim": {"quote": "교육 프로그램을 운영했습니다."},
                "verdict": "CLAIM_ONLY",
                "missing_elements": ["SITUATION", "PROCESS", "LEARNING"],
                "reason": "무시할 모델 문장",
                "follow_up_questions": [],
            }],
        })

        self.assertIn("상황", message)
        self.assertIn("수행 과정", message)
        self.assertIn("학습", message)

    def test_explains_when_no_experience_claim_exists(self):
        message = render_position_message({
            "analysis_status": "NO_EXPERIENCE_CLAIM",
            "findings": [],
        })

        self.assertIn("구체화할 경험", message)
        self.assertNotIn("기술 경험", message)
        self.assertIn("직접 수행한 행동", message)


if __name__ == "__main__":
    unittest.main()

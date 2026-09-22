import unittest
from pathlib import Path

from ai.jd_coaching.parser import build_extraction_messages
from ai.news_intelligence.contracts import NewsContext
from ai.news_intelligence.prompt import build_news_messages
from ai.position_coaching.contracts import load_experience_rubric
from ai.position_coaching.prompt import build_position_messages
from ai.prompting.common import COMMON_RULES, COMMON_RULES_VERSION, with_common_rules
from ai.writing_coaching.contracts import WritingMessageRequest
from ai.writing_coaching.prompt import build_writing_messages

ROOT = Path(__file__).parents[2]
HEADER = f"[공통 규칙 {COMMON_RULES_VERSION}]"


class CommonRulesTest(unittest.TestCase):
    def test_common_rules_come_first_then_one_blank_line_then_specific(self):
        prompt = with_common_rules("  너는 포지션 담당이다.\n  ")
        self.assertTrue(prompt.startswith(HEADER))
        self.assertTrue(prompt.endswith("\n\n너는 포지션 담당이다."))
        self.assertNotIn("\n\n\n", prompt)

    def test_rules_cover_language_grounding_injection_ids_and_schema(self):
        for phrase in ("한국어", "제공된 자료", "부족하다고 말한다", "데이터로만 취급", "받은 그대로", "JSON 스키마"):
            self.assertIn(phrase, COMMON_RULES)

    def test_every_agent_system_prompt_starts_with_common_rules(self):
        rubric = load_experience_rubric(
            ROOT / "position_coaching/resources/rubrics/experience-depth-v1.json"
        )
        documents = [{"document_id": "d1", "document_type": "SELF_INTRO", "text": "Redis로 성능을 개선했습니다."}]
        systems = {
            "jd": build_extraction_messages("회사", "백엔드", "Spring 경험")[0]["content"],
            "position": build_position_messages(rubric, {"position_name": "백엔드"}, documents, [])[0]["content"],
            "writing": build_writing_messages(
                WritingMessageRequest(message="고쳐줘", question="지원 동기", draft="초안", char_limit=500),
                {},
            )[0]["content"],
            "news": build_news_messages(
                NewsContext(corp_code="00000001", corp_name="회사", position_name="백엔드", jd_text="JD"),
                [], "최근 변화", coverage=True,
            )[0]["content"],
        }
        for agent, system in systems.items():
            with self.subTest(agent=agent):
                self.assertTrue(system.startswith(HEADER), f"{agent} 프롬프트가 공통 규칙으로 시작하지 않음")
                # 담당 고유 규칙이 뒤에 그대로 붙어 있어야 한다
                self.assertGreater(len(system), len(COMMON_RULES) + 50)

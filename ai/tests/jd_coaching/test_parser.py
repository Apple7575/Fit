import unittest

from ai.jd_coaching.parser import (
    build_evidence_decomposition_messages,
    build_extraction_messages,
    evidence_decomposition_schema,
    extraction_output_schema,
    normalize_evidence_requirements,
    normalize_role_elements,
)


class JdParserTest(unittest.TestCase):
    def test_extraction_schema_only_requests_jd_role_units(self):
        schema = extraction_output_schema()
        roles = schema["properties"]["role_elements"]

        self.assertEqual((roles["minItems"], roles["maxItems"]), (1, 8))
        self.assertNotIn(
            "evidence_requirements", roles["items"]["properties"]
        )

    def test_evidence_schema_enforces_evidence_limits(self):
        schema = evidence_decomposition_schema()
        evidence = schema["properties"]["evidence_requirements"]

        self.assertEqual((evidence["minItems"], evidence["maxItems"]), (1, 3))

    def test_evidence_prompt_forbids_stricter_requirements_than_jd(self):
        role = {
            "role_element_id": "role-001",
            "name": "REST API 개발 경험",
            "source_quote": "Python 또는 Java로 REST API 개발 경험",
        }
        messages = build_evidence_decomposition_messages(role)

        self.assertIn("최소 근거", messages[0]["content"])
        self.assertIn("명시하지 않았다면", messages[0]["content"])
        self.assertIn("대안", messages[0]["content"])

    def test_normalizes_roles_with_deterministic_ids(self):
        jd_text = "Python 기반 API 개발 및 운영 경험이 필요합니다."
        output = {
            "role_elements": [
                {"name": "API 개발 및 운영", "source_quote": jd_text}
            ]
        }

        roles = normalize_role_elements(output, jd_text)

        self.assertEqual(roles[0]["role_element_id"], "role-001")
        self.assertEqual(roles[0]["evidence_section_ids"], ["jd-role-001"])

    def test_uses_exact_role_name_as_smallest_source_quote(self):
        jd_text = "Python 데이터 분석 역량 및 차량 네트워크 통신에 대한 이해"
        output = {
            "role_elements": [
                {
                    "name": "차량 네트워크 통신에 대한 이해",
                    "source_quote": jd_text,
                }
            ]
        }

        roles = normalize_role_elements(output, jd_text)

        self.assertEqual(
            roles[0]["source_quote"], "차량 네트워크 통신에 대한 이해"
        )

    def test_adds_normalized_evidence_to_role(self):
        role = {
            "role_element_id": "role-001",
            "name": "API 개발 및 운영",
            "source_quote": "Python 기반 API 개발 및 운영 경험",
            "evidence_section_ids": ["jd-role-001"],
        }
        output = {
            "evidence_logic": "ALL",
            "evidence_requirements": [
                {"description": "나열된 언어 중 하나를 사용한 경험"},
                {"description": "API를 개발한 경험"},
                {"description": "API를 운영한 경험"},
            ],
        }

        normalized = normalize_evidence_requirements(role, output)

        self.assertEqual(normalized["evidence_logic"], "ALL")
        self.assertEqual(
            normalized["evidence_requirements"][0]["evidence_requirement_id"],
            "role-001-evidence-001",
        )

    def test_rejects_source_quote_not_present_in_jd(self):
        output = {
            "role_elements": [
                {"name": "백엔드 개발", "source_quote": "JD에 없는 문장"}
            ]
        }

        with self.assertRaisesRegex(ValueError, "source_quote"):
            normalize_role_elements(output, "Java 서버 개발 경험을 우대합니다.")

    def test_maps_pdf_bullet_and_whitespace_difference_to_exact_source(self):
        jd_text = (
            "- 모방학습 및 강화학습 기반 Foundation Model 개발\n"
            "· 모방학습을 이용한 비정형작업 자동화 기술개발\n"
            "· 강화학습을 이용한 Robot Foundation Model 개발"
        )
        output = {
            "role_elements": [
                {
                    "name": "Foundation Model 개발 역량",
                    "source_quote": (
                        "-모방학습을 이용한 비정형작업 자동화 기술개발\n"
                        "· 강화학습을 이용한 Robot Foundation Model 개발"
                    ),
                }
            ]
        }

        roles = normalize_role_elements(output, jd_text)

        self.assertEqual(
            roles[0]["source_quote"],
            (
                "모방학습을 이용한 비정형작업 자동화 기술개발\n"
                "· 강화학습을 이용한 Robot Foundation Model 개발"
            ),
        )

    def test_rejects_multiple_requirements_under_any_logic(self):
        role = {
            "role_element_id": "role-001",
            "name": "프로그래밍 언어 경험",
            "source_quote": "Python 또는 Java 개발 경험",
            "evidence_section_ids": ["jd-role-001"],
        }
        output = {
            "evidence_logic": "ANY",
            "evidence_requirements": [
                {"description": "Python 경험"},
                {"description": "Java 경험"},
            ],
        }

        with self.assertRaisesRegex(ValueError, "ANY role"):
            normalize_evidence_requirements(role, output)


if __name__ == "__main__":
    unittest.main()

import json
import unittest
from pathlib import Path

from ai.jd_coaching.judge import (
    build_judge_messages,
    compare_with_draft,
    derive_labels,
    judge_output_schema,
    select_connection_cases,
    select_relevant_document_sections,
    validate_judge_output,
)


ROOT = Path(__file__).parents[2]
CASE = json.loads(
    (
        ROOT
        / "evals"
        / "jd_coaching"
        / "cases"
        / "samsung-ds-global-manufacturing-sw-intern-001.json"
    ).read_text(encoding="utf-8")
)
DOCUMENT = json.loads(
    (
        ROOT
        / "evals"
        / "jd_coaching"
        / "sources"
        / "samsung-ds-global-manufacturing-sw-intern-2026.json"
    ).read_text(encoding="utf-8")
)
POLICY = json.loads(
    (
        ROOT / "evals" / "jd_coaching" / "connection-policy-v1.json"
    ).read_text(encoding="utf-8")
)


def draft_equivalent_output() -> dict:
    judgments = []
    roles = {
        role["role_element_id"]: role for role in CASE["expected_role_elements"]
    }
    for connection in CASE["expected_connections"]:
        present = {
            item["evidence_requirement_id"]: item["evidence_quote"]
            for item in connection["present_evidence"]
        }
        judgments.append(
            {
                "role_element_id": connection["role_element_id"],
                "experience_id": connection["experience_id"],
                "evidence_checks": [
                    {
                        "evidence_requirement_id": requirement[
                            "evidence_requirement_id"
                        ],
                        "status": (
                            "PRESENT"
                            if requirement["evidence_requirement_id"] in present
                            else "ABSENT"
                        ),
                        "evidence_quote": present.get(
                            requirement["evidence_requirement_id"], ""
                        ),
                        "reason": "근거 존재 여부를 확인했다.",
                    }
                    for requirement in roles[connection["role_element_id"]][
                        "evidence_requirements"
                    ]
                ],
            }
        )
    return {"judgments": judgments}


class JudgeTest(unittest.TestCase):
    def test_selects_only_sections_referenced_by_single_role(self):
        selected_case = select_connection_cases(
            CASE, reference_label="PARTIALLY_SUPPORTED"
        )[0]

        selected_document = select_relevant_document_sections(
            DOCUMENT, selected_case
        )

        expected_ids = set(
            selected_case["expected_role_elements"][0][
                "evidence_section_ids"
            ]
        )
        self.assertEqual(
            {section["section_id"] for section in selected_document["sections"]},
            expected_ids,
        )
        self.assertLess(
            len(selected_document["sections"]), len(DOCUMENT["sections"])
        )

    def test_selects_partial_connections_as_independent_cases(self):
        selected = select_connection_cases(
            CASE, reference_label="PARTIALLY_SUPPORTED"
        )

        self.assertEqual(len(selected), 3)
        for item in selected:
            self.assertEqual(len(item["expected_connections"]), 1)
            self.assertEqual(len(item["expected_role_elements"]), 1)
            self.assertEqual(len(item["experiences"]), 1)
            self.assertEqual(
                item["expected_connections"][0]["label"],
                "PARTIALLY_SUPPORTED",
            )

    def test_selects_all_connections_when_label_is_omitted(self):
        selected = select_connection_cases(CASE)

        self.assertEqual(len(selected), len(CASE["expected_connections"]))

    def test_schema_uses_qwen_supported_keywords(self):
        serialized = json.dumps(judge_output_schema())

        self.assertNotIn("uniqueItems", serialized)

    def test_prompt_hides_draft_labels_and_reasons(self):
        messages = build_judge_messages(DOCUMENT, CASE, POLICY)
        model_input = json.loads(messages[1]["content"])

        self.assertNotIn("expected_connections", model_input)
        self.assertNotIn("label_status", model_input)
        self.assertNotIn("label", json.dumps(model_input))

    def test_validates_and_derives_labels(self):
        output = draft_equivalent_output()

        validate_judge_output(output, CASE)
        labels = derive_labels(output, CASE)

        self.assertEqual(len(labels), 20)
        self.assertEqual(labels[0]["derived_label"], "SUPPORTED")

    def test_rejects_quote_not_found_in_experience(self):
        output = draft_equivalent_output()
        output["judgments"][0]["evidence_checks"][0][
            "evidence_quote"
        ] = "경험에 없는 문장"

        with self.assertRaisesRegex(ValueError, "evidence_quote"):
            validate_judge_output(output, CASE)

    def test_reports_only_disagreements(self):
        output = draft_equivalent_output()
        output["judgments"][0]["evidence_checks"][0]["status"] = "ABSENT"
        output["judgments"][0]["evidence_checks"][0]["evidence_quote"] = ""

        comparison = compare_with_draft(output, CASE)

        self.assertEqual(comparison["agreement_count"], 19)
        self.assertEqual(comparison["disagreement_count"], 1)
        self.assertEqual(
            comparison["disagreements"][0]["role_element_id"], "role-01"
        )

    def test_builds_feedback_from_missing_evidence(self):
        output = draft_equivalent_output()
        output["judgments"][0]["evidence_checks"][0]["status"] = "ABSENT"
        output["judgments"][0]["evidence_checks"][0]["evidence_quote"] = ""

        connection = derive_labels(output, CASE)[0]

        self.assertEqual(connection["derived_label"], "PARTIALLY_SUPPORTED")
        self.assertEqual(
            connection["missing_evidence"][0]["description"],
            "사용한 프로그래밍 언어가 명시돼 있다.",
        )
        self.assertIn("사용한 프로그래밍 언어", connection["feedback"])


if __name__ == "__main__":
    unittest.main()

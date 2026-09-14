import copy
import json
import unittest
from pathlib import Path

from ai.jd_coaching.baseline import (
    build_messages,
    output_schema,
    score_connections,
    validate_model_output,
)


ROOT = Path(__file__).parents[2]
CASE = json.loads(
    (
        ROOT
        / "evals"
        / "jd_coaching"
        / "cases"
        / "samsung-ds-software-001.json"
    ).read_text(encoding="utf-8")
)
DOCUMENT = json.loads(
    (
        ROOT
        / "evals"
        / "jd_coaching"
        / "sources"
        / "samsung-ds-software-job-intro.json"
    ).read_text(encoding="utf-8")
)
POLICY = json.loads(
    (
        ROOT / "evals" / "jd_coaching" / "connection-policy-v1.json"
    ).read_text(encoding="utf-8")
)


def valid_prediction() -> dict:
    return {
        "connections": [
            {
                "role_element_id": item["role_element_id"],
                "experience_id": item["experience_id"],
                "label": item["label"],
                "job_evidence_section_ids": [
                    next(
                        role["evidence_section_ids"][0]
                        for role in CASE["expected_role_elements"]
                        if role["role_element_id"] == item["role_element_id"]
                    )
                ],
                "present_evidence": item["present_evidence"],
                "missing_evidence_requirement_ids": item[
                    "missing_evidence_requirement_ids"
                ],
                "reason": item["reason"],
            }
            for item in CASE["expected_connections"]
        ]
    }


class BaselineTest(unittest.TestCase):
    def test_output_schema_uses_qwen_supported_keywords(self):
        self.assertNotIn("uniqueItems", json.dumps(output_schema()))

    def test_prompt_does_not_expose_gold_labels(self):
        messages = build_messages(DOCUMENT, CASE, POLICY)
        model_input = json.loads(messages[1]["content"])

        self.assertNotIn("expected_connections", model_input)
        self.assertNotIn("label_status", model_input)
        self.assertEqual(
            len(model_input["target_connections"]),
            len(CASE["expected_connections"]),
        )
        self.assertNotIn("label", model_input["target_connections"][0])

    def test_validates_complete_prediction(self):
        validate_model_output(valid_prediction(), CASE, DOCUMENT)

    def test_rejects_missing_connection_pair(self):
        prediction = valid_prediction()
        prediction["connections"].pop()

        with self.assertRaisesRegex(ValueError, "connection pairs"):
            validate_model_output(prediction, CASE, DOCUMENT)

    def test_rejects_unknown_section(self):
        prediction = valid_prediction()
        prediction["connections"][0]["job_evidence_section_ids"] = ["unknown"]

        with self.assertRaisesRegex(ValueError, "section_id"):
            validate_model_output(prediction, CASE, DOCUMENT)

    def test_scores_labels_against_human_gold(self):
        prediction = valid_prediction()
        prediction["connections"][0]["label"] = "NOT_SUPPORTED"

        scores = score_connections(prediction, CASE)

        self.assertEqual(scores["total"], 8)
        self.assertEqual(scores["correct"], 7)
        self.assertEqual(scores["accuracy"], 0.875)
        self.assertLess(scores["macro_f1"], 1.0)
        self.assertEqual(
            scores["mismatches"],
            [
                {
                    "role_element_id": "role-01",
                    "experience_id": "exp-01",
                    "gold_label": "SUPPORTED",
                    "predicted_label": "NOT_SUPPORTED",
                }
            ],
        )

    def test_rejects_unapproved_case(self):
        draft_case = copy.deepcopy(CASE)
        draft_case["label_status"] = "DRAFT"

        with self.assertRaisesRegex(ValueError, "HUMAN_APPROVED"):
            score_connections(valid_prediction(), draft_case)


if __name__ == "__main__":
    unittest.main()

import copy
import json
import unittest
from pathlib import Path

from ai.jd_coaching.contracts import load_jd_document
from ai.jd_coaching.evaluation import (
    EvaluationContractError,
    evaluate_connection_predictions,
    summarize_evaluation_cases,
    validate_evaluation_case,
)


ROOT = Path(__file__).parents[2]
CASE_PATH = (
    ROOT
    / "evals"
    / "jd_coaching"
    / "cases"
    / "samsung-ds-software-001.json"
)
SOURCE_DIR = ROOT / "evals" / "jd_coaching" / "sources"


class EvaluationContractTest(unittest.TestCase):
    def setUp(self):
        self.case = json.loads(CASE_PATH.read_text(encoding="utf-8"))
        self.documents = {
            document.document_id: document
            for document in (
                load_jd_document(path) for path in SOURCE_DIR.glob("*.json")
            )
        }

    def test_committed_case_references_existing_evidence(self):
        case_paths = sorted(
            (
                ROOT / "evals" / "jd_coaching" / "cases"
            ).glob("*.json")
        )

        self.assertGreaterEqual(len(case_paths), 2)
        for path in case_paths:
            with self.subTest(case=path.name):
                case = json.loads(path.read_text(encoding="utf-8"))
                validate_evaluation_case(case, self.documents)

    def test_rejects_unknown_source_document(self):
        case = copy.deepcopy(self.case)
        case["source_document_ids"] = ["missing-document"]

        with self.assertRaisesRegex(EvaluationContractError, "source_document_id"):
            validate_evaluation_case(case, self.documents)

    def test_rejects_unknown_evidence_section(self):
        case = copy.deepcopy(self.case)
        case["expected_role_elements"][0]["evidence_section_ids"] = [
            "missing-section"
        ]

        with self.assertRaisesRegex(EvaluationContractError, "evidence_section_id"):
            validate_evaluation_case(case, self.documents)

    def test_rejects_connection_to_unknown_experience(self):
        case = copy.deepcopy(self.case)
        case["expected_connections"][0]["experience_id"] = "missing-experience"

        with self.assertRaisesRegex(EvaluationContractError, "experience_id"):
            validate_evaluation_case(case, self.documents)

    def test_rejects_unknown_connection_label(self):
        case = copy.deepcopy(self.case)
        case["expected_connections"][0]["label"] = "RELATED"

        with self.assertRaisesRegex(EvaluationContractError, "label"):
            validate_evaluation_case(case, self.documents)

    def test_rejects_unknown_evidence_requirement(self):
        case = copy.deepcopy(self.case)
        case["expected_connections"][0]["present_evidence"][0][
            "evidence_requirement_id"
        ] = "missing-requirement"

        with self.assertRaisesRegex(
            EvaluationContractError, "evidence_requirement_id"
        ):
            validate_evaluation_case(case, self.documents)

    def test_rejects_evidence_quote_not_found_in_experience(self):
        case = copy.deepcopy(self.case)
        case["expected_connections"][0]["present_evidence"][0][
            "evidence_quote"
        ] = "사용자 경험에 존재하지 않는 문장"

        with self.assertRaisesRegex(EvaluationContractError, "evidence_quote"):
            validate_evaluation_case(case, self.documents)

    def test_rejects_label_that_disagrees_with_evidence_coverage(self):
        case = copy.deepcopy(self.case)
        case["expected_connections"][0]["label"] = "NOT_SUPPORTED"

        with self.assertRaisesRegex(EvaluationContractError, "evidence coverage"):
            validate_evaluation_case(case, self.documents)

    def test_service_policy_and_judge_rubric_are_separate(self):
        eval_directory = ROOT / "evals" / "jd_coaching"
        policy = json.loads(
            (eval_directory / "connection-policy-v1.json").read_text(
                encoding="utf-8"
            )
        )
        rubric = json.loads(
            (eval_directory / "evaluation-rubric-v1.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(
            set(policy["labels"]),
            {"SUPPORTED", "PARTIALLY_SUPPORTED", "NOT_SUPPORTED"},
        )
        self.assertNotIn("judge_criteria", policy)
        self.assertNotIn("labels", rubric)
        self.assertEqual(
            {criterion["criterion_id"] for criterion in rubric["judge_criteria"]},
            {
                "job_evidence_faithfulness",
                "experience_evidence_faithfulness",
                "explanation_consistency",
                "missing_information_clarity",
            },
        )

    def test_computes_label_and_evidence_metrics(self):
        gold = [
            {
                "role_element_id": "role-1",
                "experience_id": "exp-1",
                "label": "SUPPORTED",
                "present_evidence": [
                    {
                        "evidence_requirement_id": "evidence-1",
                        "evidence_quote": "Python API",
                    }
                ],
            },
            {
                "role_element_id": "role-2",
                "experience_id": "exp-1",
                "label": "NOT_SUPPORTED",
                "present_evidence": [],
            },
        ]
        predictions = [
            {
                "role_element_id": "role-1",
                "experience_id": "exp-1",
                "label": "SUPPORTED",
                "present_evidence": [
                    {
                        "evidence_requirement_id": "evidence-1",
                        "evidence_quote": "Python API",
                    }
                ],
            },
            {
                "role_element_id": "role-2",
                "experience_id": "exp-1",
                "label": "PARTIALLY_SUPPORTED",
                "present_evidence": [
                    {
                        "evidence_requirement_id": "evidence-2",
                        "evidence_quote": "없는 인용문",
                    }
                ],
            },
        ]

        metrics = evaluate_connection_predictions(
            gold,
            predictions,
            {"exp-1": "Python API를 개발했습니다."},
        )

        self.assertEqual(metrics["connection_count"], 2)
        self.assertEqual(metrics["label_accuracy"], 0.5)
        self.assertEqual(metrics["prediction_coverage"], 1.0)
        self.assertEqual(metrics["evidence_requirement_precision"], 0.5)
        self.assertEqual(metrics["evidence_requirement_recall"], 1.0)
        self.assertEqual(metrics["hallucinated_quote_rate"], 0.5)

    def test_summarizes_human_approved_and_draft_labels_separately(self):
        summary = summarize_evaluation_cases(
            [
                {
                    "label_status": "HUMAN_APPROVED",
                    "expected_role_elements": [{}, {}],
                    "expected_connections": [{}, {}, {}],
                },
                {
                    "label_status": "DRAFT",
                    "expected_role_elements": [{}],
                    "expected_connections": [{}, {}],
                },
            ]
        )

        self.assertEqual(summary["human_approved"]["connections"], 3)
        self.assertEqual(summary["draft"]["connections"], 2)


if __name__ == "__main__":
    unittest.main()

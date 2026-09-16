import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

from ai.writing_coaching.contracts import CANONICAL_DIMENSIONS, WritingMessageRequest
from ai.writing_coaching.evaluation import load_cases
from ai.writing_coaching.validation import validate_writing_output


CASE_PATH = Path("ai/evals/writing_coaching/canonical-v1-cases.json")


class WritingEvaluationFixtureTest(unittest.TestCase):
    def test_repository_cases_cover_required_behaviors(self):
        cases = load_cases(CASE_PATH)
        self.assertGreaterEqual(len(cases), 12)
        self.assertEqual(len(cases), 12)
        self.assertEqual({case["label_status"] for case in cases}, {"DRAFT"})
        self.assertEqual(
            {case["expected_status"] for case in cases},
            {"REVISED", "ANSWERED", "CLARIFICATION_REQUIRED"},
        )
        self.assertEqual(
            {
                case.get("expected_strength")
                for case in cases
                if case["expected_status"] == "REVISED"
            },
            {"LIGHT", "BALANCED", "REWRITE"},
        )
        self.assertEqual(len({case["case_id"] for case in cases}), len(cases))
        for case in cases:
            self.assertIsInstance(case["request"], dict)
            self.assertIsInstance(case["review_expectations"], list)
            self.assertIsInstance(case["forbidden_outputs"], list)
            self.assertEqual(
                [item["dimension"] for item in case["review_expectations"]],
                list(CANONICAL_DIMENSIONS),
            )
            self.assertTrue(case["forbidden_outputs"])

    def test_loader_rejects_duplicate_ids_and_non_draft_labels(self):
        cases = load_cases(CASE_PATH)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"

            duplicate = {"cases": [*cases, copy.deepcopy(cases[0])]}
            path.write_text(json.dumps(duplicate, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_cases(path)

            non_draft = copy.deepcopy(cases)
            non_draft[0]["label_status"] = "HUMAN_APPROVED"
            path.write_text(
                json.dumps({"cases": non_draft}, ensure_ascii=False), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "DRAFT"):
                load_cases(path)

    def test_loader_rejects_missing_contract_fields(self):
        cases = load_cases(CASE_PATH)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            for field in ("case_id", "request", "review_expectations", "forbidden_outputs"):
                invalid = copy.deepcopy(cases)
                invalid[0].pop(field, None)
                path.write_text(
                    json.dumps({"cases": invalid}, ensure_ascii=False), encoding="utf-8"
                )
                with self.subTest(field=field), self.assertRaises(ValueError):
                    load_cases(path)

    def test_loader_requires_valid_strength_for_revised_cases(self):
        cases = load_cases(CASE_PATH)
        revised_index = next(
            index for index, case in enumerate(cases) if case["expected_status"] == "REVISED"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            for strength in (None, "HEAVY"):
                invalid = copy.deepcopy(cases)
                if strength is None:
                    invalid[revised_index].pop("expected_strength")
                else:
                    invalid[revised_index]["expected_strength"] = strength
                path.write_text(
                    json.dumps({"cases": invalid}, ensure_ascii=False), encoding="utf-8"
                )
                with self.subTest(strength=strength), self.assertRaisesRegex(
                    ValueError, "expected_strength"
                ):
                    load_cases(path)

    def test_loader_requires_nonempty_canonical_expectations(self):
        cases = load_cases(CASE_PATH)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            for expectations in ([], [{"dimension": "UNKNOWN", "expectation": "내용"}]):
                invalid = copy.deepcopy(cases)
                invalid[0]["review_expectations"] = expectations
                path.write_text(
                    json.dumps({"cases": invalid}, ensure_ascii=False), encoding="utf-8"
                )
                with self.subTest(expectations=expectations), self.assertRaisesRegex(
                    ValueError, "review_expectations"
                ):
                    load_cases(path)

    def test_loader_requires_nonempty_forbidden_output_strings(self):
        cases = load_cases(CASE_PATH)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            for forbidden in ([], ["  ", 3]):
                invalid = copy.deepcopy(cases)
                invalid[0]["forbidden_outputs"] = forbidden
                path.write_text(
                    json.dumps({"cases": invalid}, ensure_ascii=False), encoding="utf-8"
                )
                with self.subTest(forbidden=forbidden), self.assertRaisesRegex(
                    ValueError, "forbidden_outputs"
                ):
                    load_cases(path)

    def test_api_revised_example_is_valid_against_current_contract(self):
        api_doc = Path("docs/api/writing-agent-api.md").read_text(encoding="utf-8")
        request_match = re.search(r"## 요청.*?```json\n(.*?)```", api_doc, re.DOTALL)
        response_match = re.search(r"### REVISED.*?```json\n(.*?)```", api_doc, re.DOTALL)
        self.assertIsNotNone(request_match)
        self.assertIsNotNone(response_match)
        request = WritingMessageRequest.model_validate(json.loads(request_match.group(1)))
        response = json.loads(response_match.group(1))
        validate_writing_output(response, request)


if __name__ == "__main__":
    unittest.main()

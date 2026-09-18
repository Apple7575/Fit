import copy
import json
import unittest
from pathlib import Path

from ai.position_coaching.contracts import (
    CLAIM_TYPES,
    load_experience_rubric,
    validate_documents,
    validate_experience_analysis_output,
)


ROOT = Path(__file__).parents[2]
RUBRIC = ROOT / "position_coaching/resources/rubrics/experience-depth-v1.json"
SCHEMA = ROOT / "position_coaching/resources/schemas/position-analysis-v2.json"
EXPECTED_CLAIM_TYPES = {
    "PROBLEM_SOLVING": ("PROBLEM", "ROLE", "ACTION", "REASONING", "VERIFICATION", "RESULT"),
    "ACHIEVEMENT": ("SITUATION", "ROLE", "ACTION", "VERIFICATION", "RESULT"),
    "DECISION": ("SITUATION", "ROLE", "ACTION", "REASONING", "RESULT"),
    "EXECUTION": ("SITUATION", "ROLE", "ACTION", "PROCESS", "RESULT"),
    "COLLABORATION": ("SITUATION", "ROLE", "ACTION", "PROCESS", "RESULT"),
    "GROWTH": ("SITUATION", "ACTION", "VERIFICATION", "LEARNING"),
    "OTHER": ("SITUATION", "ROLE", "ACTION", "RESULT"),
}
DOCUMENTS = [{
    "document_id": "essay-v2", "document_type": "SELF_INTRO",
    "text": "SNS 캠페인을 개선해 전환율을 높였습니다.",
}]


def valid_output():
    quote = DOCUMENTS[0]["text"]
    return {
        "analysis_status": "COMPLETED",
        "rubric": {"id": "experience-depth-v1", "version": 1},
        "findings": [{
            "finding_id": "finding-001", "claim_type": "ACHIEVEMENT",
            "claim": {"quote": quote, "document_id": "essay-v2", "start_offset": 0, "end_offset": len(quote)},
            "present_elements": [],
            "missing_elements": ["SITUATION", "ROLE", "ACTION", "VERIFICATION", "RESULT"],
            "verdict": "CLAIM_ONLY",
            "reason": "추상적인 개선 주장만 있고 구체적 행동과 결과 근거가 없습니다.",
            "follow_up_questions": ["어떤 지표를 어떻게 비교했나요?"],
        }],
        "model_metadata": {
            "base_model": "main", "base_revision": "deployment-alias-unresolved",
            "adapter": None, "training_dataset": None, "prompt_version": "experience-depth-v1",
        },
    }


class ExperienceDepthRubricTest(unittest.TestCase):
    def test_loads_canonical_claim_types(self):
        rubric = load_experience_rubric(RUBRIC)
        actual = {item["code"]: tuple(item["required_elements"]) for item in rubric["claim_types"]}
        self.assertEqual(actual, EXPECTED_CLAIM_TYPES)
        self.assertEqual(CLAIM_TYPES, EXPECTED_CLAIM_TYPES)

    def test_rejects_legacy_profile_shape(self):
        with self.assertRaisesRegex(ValueError, "rubric_id"):
            load_experience_rubric({"schema_version": "1.0", "profile_id": "backend-v1"})

    def test_rejects_reordered_or_unknown_required_elements(self):
        for replacement in (["ACTION", "SITUATION", "ROLE", "VERIFICATION", "RESULT"], ["UNKNOWN"]):
            payload = json.loads(RUBRIC.read_text(encoding="utf-8"))
            payload["claim_types"][1]["required_elements"] = replacement
            with self.subTest(replacement=replacement), self.assertRaisesRegex(ValueError, "required_elements"):
                load_experience_rubric(payload)

    def test_rejects_duplicate_claim_type(self):
        payload = json.loads(RUBRIC.read_text(encoding="utf-8"))
        payload["claim_types"].append(copy.deepcopy(payload["claim_types"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate claim type"):
            load_experience_rubric(payload)


class DocumentContractTest(unittest.TestCase):
    def test_rejects_duplicate_ids_blank_text_and_unsupported_type(self):
        variants = [
            [DOCUMENTS[0], DOCUMENTS[0]],
            [{**DOCUMENTS[0], "text": "  "}],
            [{**DOCUMENTS[0], "document_type": "JOB_DESCRIPTION"}],
        ]
        for documents in variants:
            with self.subTest(documents=documents), self.assertRaises(ValueError):
                validate_documents(documents)


class ExperienceAnalysisOutputTest(unittest.TestCase):
    def setUp(self):
        self.rubric = load_experience_rubric(RUBRIC)

    def validate(self, output):
        return validate_experience_analysis_output(output, DOCUMENTS, self.rubric)

    def test_accepts_vague_claim_with_all_required_elements_missing(self):
        self.assertEqual(self.validate(valid_output())["findings"][0]["verdict"], "CLAIM_ONLY")

    def test_accepts_sufficient_with_full_coverage_and_no_questions(self):
        output = valid_output()
        finding = output["findings"][0]
        finding["present_elements"] = [{"element": element, "quote": finding["claim"]["quote"]} for element in EXPECTED_CLAIM_TYPES["ACHIEVEMENT"]]
        finding["missing_elements"] = []
        finding["verdict"] = "SUFFICIENT"
        finding["follow_up_questions"] = []
        self.assertEqual(self.validate(output)["findings"][0]["verdict"], "SUFFICIENT")

    def test_accepts_no_experience_claim_with_empty_findings(self):
        output = valid_output()
        output["analysis_status"] = "NO_EXPERIENCE_CLAIM"
        output["findings"] = []
        self.assertEqual(self.validate(output)["findings"], [])

    def test_rejects_nonempty_no_experience_claim(self):
        output = valid_output()
        output["analysis_status"] = "NO_EXPERIENCE_CLAIM"
        with self.assertRaisesRegex(ValueError, "empty findings"):
            self.validate(output)

    def test_rejects_extra_or_missing_claim_type_element(self):
        variants = []
        extra = valid_output()
        extra["findings"][0]["present_elements"] = [{"element": "LEARNING", "quote": "개선"}]
        variants.append(extra)
        omitted = valid_output()
        omitted["findings"][0]["missing_elements"].remove("RESULT")
        variants.append(omitted)
        for output in variants:
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, "element coverage"):
                self.validate(output)

    def test_rejects_duplicate_element_coverage(self):
        output = valid_output()
        output["findings"][0]["missing_elements"].append("ACTION")
        with self.assertRaisesRegex(ValueError, "element coverage"):
            self.validate(output)

    def test_rejects_verdict_disagreeing_with_coverage(self):
        output = valid_output()
        output["findings"][0]["verdict"] = "PARTIAL"
        with self.assertRaisesRegex(ValueError, "verdict"):
            self.validate(output)

    def test_rejects_fabricated_quote_wrong_offset_and_unknown_document(self):
        variants = []
        fabricated = valid_output()
        fabricated["findings"][0]["claim"]["quote"] = "전환율을 30% 높였습니다."
        variants.append(fabricated)
        wrong_offset = valid_output()
        wrong_offset["findings"][0]["claim"]["end_offset"] -= 1
        variants.append(wrong_offset)
        unknown_document = valid_output()
        unknown_document["findings"][0]["claim"]["document_id"] = "unknown"
        variants.append(unknown_document)
        for output in variants:
            with self.subTest(output=output), self.assertRaises(ValueError):
                self.validate(output)

    def test_rejects_unknown_fields_and_boolean_version(self):
        variants = []
        unknown = valid_output()
        unknown["extra"] = True
        variants.append(unknown)
        boolean_version = valid_output()
        boolean_version["rubric"]["version"] = True
        variants.append(boolean_version)
        for output in variants:
            with self.subTest(output=output), self.assertRaises(ValueError):
                self.validate(output)

    def test_rejects_duplicate_finding_ids_and_more_than_two_questions(self):
        duplicate = valid_output()
        duplicate["findings"].append(copy.deepcopy(duplicate["findings"][0]))
        too_many = valid_output()
        too_many["findings"][0]["follow_up_questions"] = ["1?", "2?", "3?"]
        for output in (duplicate, too_many):
            with self.subTest(output=output), self.assertRaises(ValueError):
                self.validate(output)


class PositionAnalysisSchemaTest(unittest.TestCase):
    def test_schema_forbids_unknown_properties_and_limits_questions(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        objects = []
        def collect(value):
            if isinstance(value, dict):
                if value.get("type") == "object":
                    objects.append(value)
                for item in value.values():
                    collect(item)
            elif isinstance(value, list):
                for item in value:
                    collect(item)
        collect(schema)
        self.assertTrue(objects)
        self.assertTrue(all(item.get("additionalProperties") is False for item in objects))
        follow_ups = schema["properties"]["findings"]["items"]["properties"]["follow_up_questions"]
        self.assertEqual(follow_ups["maxItems"], 2)


if __name__ == "__main__":
    unittest.main()

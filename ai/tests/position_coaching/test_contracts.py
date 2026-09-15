import json
import unittest
from pathlib import Path

from ai.position_coaching.contracts import (
    load_position_profile,
    validate_analysis_output,
    validate_documents,
)


ROOT = Path(__file__).parents[2]
PROFILE = ROOT / "position_coaching/resources/profiles/backend-v1.json"
SCHEMA = ROOT / "position_coaching/resources/schemas/position-analysis-v1.json"


def valid_output():
    return {
        "analysis_status": "COMPLETED",
        "position_profile": {"id": "backend-v1", "version": 1},
        "findings": [{
            "finding_id": "position-finding-001",
            "experience_type": "CACHE_PERFORMANCE",
            "claim": {
                "quote": "Redis를 활용해 서비스 성능을 개선했습니다.",
                "document_id": "essay-1",
                "start_offset": 0,
                "end_offset": 26,
            },
            "present_elements": [{"element": "ACTION", "quote": "Redis를 활용해"}],
            "missing_elements": ["PROBLEM", "MECHANISM", "VERIFICATION", "RESULT"],
            "verdict": "PARTIAL",
            "reason": "사용 기술은 확인되지만 적용 방식과 검증 결과가 없습니다.",
            "follow_up_questions": ["어떤 요청에서 성능 문제가 발생했나요?"],
        }],
        "model_metadata": {
            "base_model": "main",
            "base_revision": "deployment-alias-unresolved",
            "adapter": None,
            "training_dataset": None,
            "prompt_version": "position-depth-v1",
        },
    }


class PositionContractsTest(unittest.TestCase):
    def test_output_schema_limits_follow_up_questions_to_two(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

        follow_up_questions = (
            schema["properties"]["findings"]["items"]["properties"]
            ["follow_up_questions"]
        )

        self.assertEqual(follow_up_questions["maxItems"], 2)

    def test_loads_backend_profile_with_unique_experience_types(self):
        profile = load_position_profile(PROFILE)
        self.assertEqual(profile["profile_id"], "backend-v1")
        self.assertEqual(profile["version"], 1)
        self.assertEqual(
            len(profile["experience_types"]),
            len({item["code"] for item in profile["experience_types"]}),
        )

    def test_rejects_unknown_required_element(self):
        payload = json.loads(PROFILE.read_text(encoding="utf-8"))
        payload["experience_types"][0]["required_elements"] = ["UNKNOWN"]
        with self.assertRaisesRegex(ValueError, "required_elements"):
            load_position_profile(payload)

    def test_rejects_duplicate_document_ids(self):
        documents = [
            {"document_id": "essay-1", "document_type": "SELF_INTRO", "text": "첫 문서"},
            {"document_id": "essay-1", "document_type": "RESUME", "text": "둘째 문서"},
        ]
        with self.assertRaisesRegex(ValueError, "duplicate document_id"):
            validate_documents(documents)

    def test_rejects_whitespace_only_document_id(self):
        documents = [
            {"document_id": " ", "document_type": "SELF_INTRO", "text": "내용"},
        ]
        with self.assertRaisesRegex(ValueError, "document_id"):
            validate_documents(documents)

    def test_rejects_whitespace_only_document_text(self):
        documents = [
            {"document_id": "essay-1", "document_type": "SELF_INTRO", "text": "\t \n"},
        ]
        with self.assertRaisesRegex(ValueError, "text"):
            validate_documents(documents)

    def test_rejects_unsupported_document_type(self):
        documents = [
            {"document_id": "essay-1", "document_type": "COVER_LETTER", "text": "내용"},
        ]
        with self.assertRaisesRegex(ValueError, "document_type"):
            validate_documents(documents)

    def test_rejects_more_than_two_follow_up_questions(self):
        output = valid_output()
        output["findings"][0]["follow_up_questions"] = ["질문 1", "질문 2", "질문 3"]

        with self.assertRaisesRegex(ValueError, "at most two"):
            validate_analysis_output(
                output,
                [{
                    "document_id": "essay-1",
                    "document_type": "SELF_INTRO",
                    "text": "Redis를 활용해 서비스 성능을 개선했습니다.",
                }],
                load_position_profile(PROFILE),
            )

    def test_rejects_follow_up_question_for_sufficient_finding(self):
        output = valid_output()
        output["findings"][0]["experience_type"] = "OTHER_BACKEND"
        output["findings"][0]["present_elements"] = [
            {"element": "PROBLEM", "quote": "서비스 성능"},
            {"element": "ROLE", "quote": "Redis를 활용해"},
            {"element": "ACTION", "quote": "Redis를 활용해"},
            {"element": "RESULT", "quote": "성능을 개선"},
        ]
        output["findings"][0]["missing_elements"] = []
        output["findings"][0]["verdict"] = "SUFFICIENT"

        with self.assertRaisesRegex(ValueError, "SUFFICIENT"):
            validate_analysis_output(
                output,
                [{
                    "document_id": "essay-1",
                    "document_type": "SELF_INTRO",
                    "text": "Redis를 활용해 서비스 성능을 개선했습니다.",
                }],
                load_position_profile(PROFILE),
            )

    def test_rejects_empty_experience_types(self):
        payload = json.loads(PROFILE.read_text(encoding="utf-8"))
        payload["experience_types"] = []
        with self.assertRaisesRegex(ValueError, "experience_types"):
            load_position_profile(payload)

    def test_rejects_mapping_with_noncanonical_experience_type_codes(self):
        payload = json.loads(PROFILE.read_text(encoding="utf-8"))
        payload["experience_types"][0]["code"] = "CUSTOM_BACKEND"
        with self.assertRaisesRegex(ValueError, "experience_types"):
            load_position_profile(payload)


class PositionAnalysisOutputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = validate_documents([{
            "document_id": "essay-1",
            "document_type": "SELF_INTRO",
            "text": "Redis를 활용해 서비스 성능을 개선했습니다.",
        }])
        cls.profile = load_position_profile(PROFILE)

    def test_returns_normalized_valid_output(self):
        # Break caught: returning a placeholder or rejecting correctly formed evidence.
        self.assertEqual(
            validate_analysis_output(valid_output(), self.documents, self.profile),
            valid_output(),
        )

    def test_rejects_quote_with_wrong_offsets(self):
        # Break caught: accepting an end offset that does not delimit the quoted claim.
        output = valid_output()
        output["findings"][0]["claim"]["end_offset"] = 25
        with self.assertRaisesRegex(ValueError, "offset"):
            validate_analysis_output(output, self.documents, self.profile)

    def test_rejects_claim_with_correct_length_at_wrong_offset(self):
        # Break caught: validating quote length without checking the source slice itself.
        output = valid_output()
        output["findings"][0]["claim"]["start_offset"] = 1
        output["findings"][0]["claim"]["end_offset"] = 27
        with self.assertRaisesRegex(ValueError, "offset"):
            validate_analysis_output(output, self.documents, self.profile)

    def test_rejects_verdict_that_disagrees_with_coverage(self):
        # Break caught: trusting a model verdict instead of deriving it from policy coverage.
        output = valid_output()
        output["findings"][0]["verdict"] = "SUFFICIENT"
        with self.assertRaisesRegex(ValueError, "verdict"):
            validate_analysis_output(output, self.documents, self.profile)

    def test_rejects_unknown_top_level_field(self):
        # Break caught: silently accepting fields outside the versioned output contract.
        output = valid_output()
        output["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "unknown field"):
            validate_analysis_output(output, self.documents, self.profile)

    def test_rejects_unknown_nested_field(self):
        # Break caught: allowing uncontracted fields inside model metadata.
        output = valid_output()
        output["model_metadata"]["temperature"] = 0
        with self.assertRaisesRegex(ValueError, "unknown field"):
            validate_analysis_output(output, self.documents, self.profile)

    def test_rejects_boolean_position_profile_version(self):
        # Break caught: accepting True as profile version 1 through Python equality.
        output = valid_output()
        output["position_profile"]["version"] = True
        with self.assertRaisesRegex(ValueError, "position_profile"):
            validate_analysis_output(output, self.documents, self.profile)

    def test_rejects_overlapping_element_coverage(self):
        # Break caught: permitting an element to be both evidenced and missing.
        output = valid_output()
        output["findings"][0]["missing_elements"].append("ACTION")
        with self.assertRaisesRegex(ValueError, "element coverage"):
            validate_analysis_output(output, self.documents, self.profile)

    def test_rejects_incomplete_element_coverage(self):
        # Break caught: permitting policy elements to disappear from both coverage lists.
        output = valid_output()
        output["findings"][0]["missing_elements"].remove("RESULT")
        with self.assertRaisesRegex(ValueError, "element coverage"):
            validate_analysis_output(output, self.documents, self.profile)

    def test_rejects_unknown_document_reference(self):
        # Break caught: accepting evidence not traceable to a supplied document.
        output = valid_output()
        output["findings"][0]["claim"]["document_id"] = "essay-404"
        with self.assertRaisesRegex(ValueError, "document_id"):
            validate_analysis_output(output, self.documents, self.profile)

    def test_rejects_unknown_experience_type(self):
        # Break caught: evaluating a category absent from the validated position policy.
        output = valid_output()
        output["findings"][0]["experience_type"] = "FRONTEND"
        with self.assertRaisesRegex(ValueError, "experience_type"):
            validate_analysis_output(output, self.documents, self.profile)

    def test_rejects_present_element_quote_outside_claim(self):
        # Break caught: accepting element evidence that is not part of the cited claim.
        output = valid_output()
        output["findings"][0]["present_elements"][0]["quote"] = "없는 근거"
        with self.assertRaisesRegex(ValueError, "present element quote"):
            validate_analysis_output(output, self.documents, self.profile)

    def test_accepts_claim_only_when_empty_evidence_is_assessable(self):
        # Break caught: reclassifying assessable empty evidence as NOT_ASSESSABLE.
        output = valid_output()
        finding = output["findings"][0]
        finding["present_elements"] = []
        finding["missing_elements"] = [
            "PROBLEM", "ACTION", "MECHANISM", "VERIFICATION", "RESULT",
        ]
        finding["verdict"] = "CLAIM_ONLY"
        self.assertEqual(
            validate_analysis_output(output, self.documents, self.profile)["findings"][0]["verdict"],
            "CLAIM_ONLY",
        )

    def test_accepts_sufficient_when_all_policy_elements_are_evidenced(self):
        # Break caught: rejecting a complete policy coverage as partial.
        output = valid_output()
        finding = output["findings"][0]
        finding["present_elements"] = [
            {"element": "PROBLEM", "quote": "Redis를 활용해"},
            {"element": "ACTION", "quote": "Redis를 활용해"},
            {"element": "MECHANISM", "quote": "Redis를 활용해"},
            {"element": "VERIFICATION", "quote": "Redis를 활용해"},
            {"element": "RESULT", "quote": "Redis를 활용해"},
        ]
        finding["missing_elements"] = []
        finding["verdict"] = "SUFFICIENT"
        finding["follow_up_questions"] = []
        self.assertEqual(
            validate_analysis_output(output, self.documents, self.profile)["findings"][0]["verdict"],
            "SUFFICIENT",
        )

    def test_accepts_not_assessable_with_full_missing_coverage(self):
        # Break caught: deriving CLAIM_ONLY before honoring the explicit NOT_ASSESSABLE state.
        output = valid_output()
        finding = output["findings"][0]
        finding["present_elements"] = []
        finding["missing_elements"] = [
            "PROBLEM", "ACTION", "MECHANISM", "VERIFICATION", "RESULT",
        ]
        finding["verdict"] = "NOT_ASSESSABLE"
        finding["reason"] = "지원자 서술에 평가 가능한 행동 근거가 없습니다."
        self.assertEqual(
            validate_analysis_output(output, self.documents, self.profile)["findings"][0]["verdict"],
            "NOT_ASSESSABLE",
        )

    def test_rejects_not_assessable_without_reason(self):
        # Break caught: accepting a non-assessable decision without an explanation.
        output = valid_output()
        finding = output["findings"][0]
        finding["present_elements"] = []
        finding["missing_elements"] = [
            "PROBLEM", "ACTION", "MECHANISM", "VERIFICATION", "RESULT",
        ]
        finding["verdict"] = "NOT_ASSESSABLE"
        finding["reason"] = ""
        with self.assertRaisesRegex(ValueError, "reason"):
            validate_analysis_output(output, self.documents, self.profile)

    def test_rejects_not_assessable_without_all_policy_elements_missing(self):
        # Break caught: treating a partial missing list as an explicit non-assessable finding.
        output = valid_output()
        finding = output["findings"][0]
        finding["present_elements"] = []
        finding["missing_elements"] = ["PROBLEM", "ACTION", "MECHANISM", "VERIFICATION"]
        finding["verdict"] = "NOT_ASSESSABLE"
        with self.assertRaisesRegex(ValueError, "NOT_ASSESSABLE"):
            validate_analysis_output(output, self.documents, self.profile)

    def test_rejects_not_assessable_with_present_elements(self):
        # Break caught: allowing NOT_ASSESSABLE after the model supplied evidence.
        output = valid_output()
        output["findings"][0]["verdict"] = "NOT_ASSESSABLE"
        with self.assertRaisesRegex(ValueError, "NOT_ASSESSABLE"):
            validate_analysis_output(output, self.documents, self.profile)

    def test_revalidates_document_types_at_the_output_boundary(self):
        # Break caught: trusting an unsupported input document type while checking evidence.
        documents = [{
            "document_id": "essay-1",
            "document_type": "JOB_DESCRIPTION",
            "text": "Redis를 활용해 서비스 성능을 개선했습니다.",
        }]
        with self.assertRaisesRegex(ValueError, "document_type"):
            validate_analysis_output(valid_output(), documents, self.profile)


class PositionAnalysisSchemaTest(unittest.TestCase):
    def test_disallows_unknown_properties_at_every_object_layer(self):
        # Break caught: a schema object allowing model-generated fields outside the contract.
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        object_schemas = []

        def collect_object_schemas(value):
            if isinstance(value, dict):
                if value.get("type") == "object":
                    object_schemas.append(value)
                for item in value.values():
                    collect_object_schemas(item)
            elif isinstance(value, list):
                for item in value:
                    collect_object_schemas(item)

        collect_object_schemas(schema)
        self.assertGreater(len(object_schemas), 0)
        self.assertTrue(
            all(item.get("additionalProperties") is False for item in object_schemas)
        )

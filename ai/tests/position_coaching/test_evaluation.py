import copy
import json
import tempfile
import unittest
from pathlib import Path

from ai.position_coaching.evaluation import load_evaluation_case, score_evaluation
from ai.scripts.validate_position_eval_set import main, validate_evaluation_set


CASE_PATH = Path("ai/evals/position_coaching/cases/smoke-001.json")
POLICY_PATH = Path("ai/evals/position_coaching/evaluation-policy-v1.json")
VERDICTS = ("SUFFICIENT", "PARTIAL", "CLAIM_ONLY", "NOT_ASSESSABLE")
EXPERIENCE_TYPES = (
    "API_DESIGN",
    "DATABASE",
    "CONCURRENCY",
    "CACHE_PERFORMANCE",
    "MESSAGING",
    "RELIABILITY",
)


def actual_finding(
    *,
    verdict="PARTIAL",
    present=None,
    missing=None,
    experience_type="CACHE_PERFORMANCE",
    quote="Redis를 활용해 서비스 성능을 개선했습니다.",
    finding_id="finding-1",
):
    present = ["ACTION"] if present is None else present
    missing = (
        ["PROBLEM", "MECHANISM", "VERIFICATION", "RESULT"]
        if missing is None
        else missing
    )
    return {
        "finding_id": finding_id,
        "experience_type": experience_type,
        "claim": {
            "quote": quote,
            "document_id": "essay-1",
            "start_offset": 0,
            "end_offset": len(quote),
        },
        "present_elements": [
            {"element": element, "quote": "Redis"} for element in present
        ],
        "missing_elements": missing,
        "verdict": verdict,
        "reason": "독립 작성된 테스트 판단입니다.",
        "follow_up_questions": [],
    }


def output_with(findings):
    return {
        "analysis_status": "COMPLETED" if findings else "NO_TECHNICAL_CLAIM",
        "position_profile": {"id": "backend-v1", "version": 1},
        "findings": findings,
        "model_metadata": {
            "base_model": "fixture-model",
            "base_revision": "fixture-revision",
            "adapter": None,
            "training_dataset": None,
            "prompt_version": "fixture-v1",
        },
    }


def valid_prediction(findings=None, response_text="safe response"):
    return {
        "schema_valid": True,
        "output": output_with([actual_finding()] if findings is None else findings),
        "response_text": response_text,
    }


def approved_smoke_case():
    case = load_evaluation_case(CASE_PATH)
    case["label_status"] = "HUMAN_APPROVED"
    return case


def evaluation_case(index, verdict, experience_type, *, status="HUMAN_APPROVED"):
    required_by_type = {
        "API_DESIGN": ["PROBLEM", "ROLE", "ACTION", "REASONING", "VERIFICATION"],
        "DATABASE": ["PROBLEM", "ACTION", "MECHANISM", "VERIFICATION"],
        "CONCURRENCY": ["PROBLEM", "ACTION", "MECHANISM", "VERIFICATION"],
        "CACHE_PERFORMANCE": ["PROBLEM", "ACTION", "MECHANISM", "VERIFICATION", "RESULT"],
        "MESSAGING": ["PROBLEM", "ACTION", "MECHANISM", "VERIFICATION"],
        "RELIABILITY": ["PROBLEM", "ACTION", "REASONING", "VERIFICATION", "RESULT"],
    }
    required = required_by_type[experience_type]
    if verdict == "SUFFICIENT":
        present, missing = required, []
    elif verdict == "PARTIAL":
        present, missing = ["ACTION"], [item for item in required if item != "ACTION"]
    elif verdict == "CLAIM_ONLY":
        present, missing = [], required
    else:
        present, missing = [], required
    text = f"독립 평가 문서 {index} {verdict} {experience_type}"
    return {
        "schema_version": "1.0",
        "case_id": f"case-{index:03d}",
        "label_status": status,
        "position_profile_id": "backend-v1",
        "question": "백엔드 경험을 설명해 주세요.",
        "documents": [
            {"document_id": "essay-1", "document_type": "SELF_INTRO", "text": text}
        ],
        "expected_findings": [
            {
                "experience_type": experience_type,
                "claim_quote": text,
                "verdict": verdict,
                "present_elements": present,
                "missing_elements": missing,
            }
        ],
        "forbidden_output_substrings": ["합격"],
    }


def valid_set():
    return [
        evaluation_case(index, VERDICTS[index // 15], EXPERIENCE_TYPES[index % 6])
        for index in range(60)
    ]


class EvaluationCaseLoadingTest(unittest.TestCase):
    def test_refuses_to_score_draft_cases(self):
        # Break caught: repository DRAFT labels being treated as approved truth.
        case = load_evaluation_case(CASE_PATH)
        with self.assertRaisesRegex(ValueError, "HUMAN_APPROVED"):
            score_evaluation([case], {case["case_id"]: valid_prediction()})

    def test_repository_smoke_case_remains_draft(self):
        # Break caught: implementation silently promoting an unreviewed fixture.
        self.assertEqual(load_evaluation_case(CASE_PATH)["label_status"], "DRAFT")

    def test_loader_rejects_unknown_fields_and_wrong_types(self):
        # Break caught: schema drift or Python bool/int coercion bypassing strict loading.
        base = json.loads(CASE_PATH.read_text(encoding="utf-8"))
        mutations = []
        unknown = copy.deepcopy(base)
        unknown["unreviewed_note"] = "ignored"
        mutations.append(unknown)
        wrong_documents = copy.deepcopy(base)
        wrong_documents["documents"] = {"document_id": "essay-1"}
        mutations.append(wrong_documents)
        wrong_status = copy.deepcopy(base)
        wrong_status["label_status"] = True
        mutations.append(wrong_status)
        with tempfile.TemporaryDirectory() as directory:
            for index, payload in enumerate(mutations):
                with self.subTest(index=index):
                    path = Path(directory) / f"case-{index}.json"
                    path.write_text(json.dumps(payload), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_evaluation_case(path)

    def test_loader_rejects_invalid_references_partitions_and_duplicate_keys(self):
        # Break caught: trusting labels whose profile, quote, element partition, or identity is invalid.
        base = json.loads(CASE_PATH.read_text(encoding="utf-8"))
        mutations = []
        bad_profile = copy.deepcopy(base)
        bad_profile["position_profile_id"] = "frontend-v1"
        mutations.append(bad_profile)
        duplicate_document = copy.deepcopy(base)
        duplicate_document["documents"].append(copy.deepcopy(duplicate_document["documents"][0]))
        mutations.append(duplicate_document)
        absent_quote = copy.deepcopy(base)
        absent_quote["expected_findings"][0]["claim_quote"] = "문서에 없는 근거"
        mutations.append(absent_quote)
        invalid_partition = copy.deepcopy(base)
        invalid_partition["expected_findings"][0]["missing_elements"].append("ACTION")
        mutations.append(invalid_partition)
        wrong_verdict = copy.deepcopy(base)
        wrong_verdict["expected_findings"][0]["verdict"] = "SUFFICIENT"
        mutations.append(wrong_verdict)
        duplicate_key = copy.deepcopy(base)
        duplicate_key["expected_findings"].append(copy.deepcopy(duplicate_key["expected_findings"][0]))
        mutations.append(duplicate_key)
        with tempfile.TemporaryDirectory() as directory:
            for index, payload in enumerate(mutations):
                with self.subTest(index=index):
                    path = Path(directory) / f"case-{index}.json"
                    path.write_text(json.dumps(payload), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_evaluation_case(path)


class EvaluationScoringTest(unittest.TestCase):
    def test_perfect_prediction_has_perfect_defined_metrics(self):
        # Break caught: changing alignment or metric arithmetic for a fully matching finding.
        case = approved_smoke_case()
        result = score_evaluation([case], {case["case_id"]: valid_prediction()})

        self.assertEqual(result["prediction_coverage"], {"numerator": 1, "denominator": 1, "rate": 1.0})
        self.assertEqual(result["schema_valid_response_rate"], {"numerator": 1, "denominator": 1, "rate": 1.0})
        self.assertEqual(result["verdict_accuracy"]["rate"], 1.0)
        self.assertEqual(result["present_elements"]["f1"]["rate"], 1.0)
        self.assertEqual(result["missing_elements"]["f1"]["rate"], 1.0)
        self.assertEqual(result["exact_claim_quote_rate"]["rate"], 1.0)

    def test_imperfect_elements_report_hand_checked_counts(self):
        # Break caught: hiding false-positive elements or computing recall as precision.
        case = approved_smoke_case()
        finding = actual_finding(
            present=["ACTION", "PROBLEM"],
            missing=["MECHANISM", "VERIFICATION", "RESULT"],
        )
        result = score_evaluation([case], {case["case_id"]: valid_prediction([finding])})

        self.assertEqual(result["present_elements"]["precision"], {"numerator": 1, "denominator": 2, "rate": 0.5})
        self.assertEqual(result["present_elements"]["recall"], {"numerator": 1, "denominator": 1, "rate": 1.0})
        self.assertEqual(result["present_elements"]["f1"], {"numerator": 2, "denominator": 3, "rate": 2 / 3})
        self.assertEqual(result["missing_elements"]["recall"], {"numerator": 3, "denominator": 4, "rate": 0.75})

    def test_missing_prediction_reduces_coverage_without_inventing_a_label(self):
        # Break caught: coercing a missing record into CLAIM_ONLY or NOT_ASSESSABLE.
        result = score_evaluation([approved_smoke_case()], {})

        self.assertEqual(result["prediction_coverage"], {"numerator": 0, "denominator": 1, "rate": 0.0})
        self.assertEqual(result["schema_valid_response_rate"], {"numerator": 0, "denominator": 0, "rate": None})
        self.assertEqual(result["verdict_accuracy"], {"numerator": 0, "denominator": 0, "rate": None})
        self.assertEqual(result["verdict_macro_f1"]["denominator"], 4)
        self.assertEqual(result["verdict_macro_f1"]["rate"], 0.0)

    def test_schema_failed_response_is_scanned_without_text_leakage(self):
        # Break caught: skipping safety scans on invalid output or leaking the rejected response.
        secret = "분산 락 secret 합격 분산 락"
        case = approved_smoke_case()
        prediction = {"schema_valid": False, "output": None, "response_text": secret}
        result = score_evaluation([case], {case["case_id"]: prediction})
        serialized = json.dumps(result, ensure_ascii=False)

        self.assertEqual(result["prediction_coverage"]["rate"], 1.0)
        self.assertEqual(result["schema_valid_response_rate"]["rate"], 0.0)
        self.assertEqual(result["forbidden_output_occurrence_count"], 3)
        self.assertNotIn(secret, serialized)
        self.assertNotIn("분산 락", serialized)

    def test_rejects_invalid_prediction_envelopes(self):
        # Break caught: accepting ambiguous envelope states that corrupt coverage semantics.
        case = approved_smoke_case()
        invalid = [
            {"schema_valid": "false", "output": None, "response_text": ""},
            {"schema_valid": False, "output": output_with([]), "response_text": ""},
            {"schema_valid": True, "output": None, "response_text": ""},
            {"schema_valid": False, "output": None, "response_text": 3},
            {"schema_valid": False, "output": None, "response_text": "", "extra": True},
        ]
        for index, envelope in enumerate(invalid):
            with self.subTest(index=index):
                with self.assertRaises(ValueError):
                    score_evaluation([case], {case["case_id"]: envelope})

    def test_rejects_duplicate_actual_finding_keys(self):
        # Break caught: dict-style alignment silently overwriting a repeated actual finding.
        case = approved_smoke_case()
        findings = [actual_finding(finding_id="one"), actual_finding(finding_id="two")]
        with self.assertRaisesRegex(ValueError, "duplicate.*finding key"):
            score_evaluation([case], {case["case_id"]: valid_prediction(findings)})

    def test_empty_inputs_expose_zero_denominators(self):
        # Break caught: division errors or reporting a perfect rate when nothing was evaluated.
        result = score_evaluation([], {})
        self.assertEqual(result["prediction_coverage"], {"numerator": 0, "denominator": 0, "rate": None})
        self.assertIsNone(result["present_elements"]["precision"]["rate"])
        self.assertIsNone(result["missing_elements"]["recall"]["rate"])
        self.assertIsNone(result["exact_claim_quote_rate"]["rate"])


class EvaluationSetValidationTest(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

    def test_accepts_exact_human_approved_distribution_and_type_coverage(self):
        # Break caught: rejecting the one policy-compliant shape.
        report = validate_evaluation_set(valid_set(), self.policy)
        self.assertTrue(report["valid"])
        self.assertEqual(report["case_count"], 60)
        self.assertEqual(report["count_by_verdict"], {verdict: 15 for verdict in VERDICTS})
        self.assertEqual(report["experience_type_count"], 6)

    def test_rejects_policy_that_shrinks_the_baseline_to_four_cases(self):
        # Break caught: caller-controlled policy values making a tiny set claim valid:true.
        bypass_policy = copy.deepcopy(self.policy)
        bypass_policy["required_case_count"] = 4
        bypass_policy["required_count_by_verdict"] = {
            verdict: 1 for verdict in VERDICTS
        }
        bypass_policy["minimum_experience_types"] = 1
        four_cases = [
            evaluation_case(index, verdict, "API_DESIGN")
            for index, verdict in enumerate(VERDICTS)
        ]

        with self.assertRaises(ValueError):
            validate_evaluation_set(four_cases, bypass_policy)

    def test_rejects_every_noncanonical_policy_dimension_and_type(self):
        # Break caught: accepting any modified field, key set, verdict count, or bool-as-int.
        mutations = []
        for field, value in (
            ("schema_version", "1.1"),
            ("profile_id", "frontend-v1"),
            ("required_case_count", 4),
            ("required_case_count", True),
            ("minimum_experience_types", 1),
            ("minimum_experience_types", True),
            ("required_label_status", "DRAFT"),
        ):
            policy = copy.deepcopy(self.policy)
            policy[field] = value
            mutations.append(policy)

        altered_distribution = copy.deepcopy(self.policy)
        altered_distribution["required_count_by_verdict"]["SUFFICIENT"] = 14
        altered_distribution["required_count_by_verdict"]["PARTIAL"] = 16
        mutations.append(altered_distribution)
        bool_distribution = copy.deepcopy(self.policy)
        bool_distribution["required_count_by_verdict"]["SUFFICIENT"] = True
        mutations.append(bool_distribution)
        missing_verdict = copy.deepcopy(self.policy)
        del missing_verdict["required_count_by_verdict"]["SUFFICIENT"]
        mutations.append(missing_verdict)
        extra_verdict = copy.deepcopy(self.policy)
        extra_verdict["required_count_by_verdict"]["UNKNOWN"] = 0
        mutations.append(extra_verdict)
        missing_field = copy.deepcopy(self.policy)
        del missing_field["minimum_experience_types"]
        mutations.append(missing_field)
        extra_field = copy.deepcopy(self.policy)
        extra_field["allow_drafts"] = True
        mutations.append(extra_field)

        for index, policy in enumerate(mutations):
            with self.subTest(index=index):
                with self.assertRaises(ValueError):
                    validate_evaluation_set([], policy)

    def test_committed_policy_matches_the_immutable_v1_contract(self):
        # Break caught: checked-in configuration drifting from the production gate.
        self.assertEqual(
            self.policy,
            {
                "schema_version": "1.0",
                "profile_id": "backend-v1",
                "required_case_count": 60,
                "required_count_by_verdict": {
                    "SUFFICIENT": 15,
                    "PARTIAL": 15,
                    "CLAIM_ONLY": 15,
                    "NOT_ASSESSABLE": 15,
                },
                "minimum_experience_types": 6,
                "required_label_status": "HUMAN_APPROVED",
            },
        )

    def test_rejects_count_distribution_type_and_approval_gate_failures(self):
        # Break caught: weakening any immutable gate needed for a comparable baseline.
        variants = []
        variants.append(valid_set()[:-1])
        wrong_distribution = valid_set()
        wrong_distribution[0] = evaluation_case(0, "PARTIAL", EXPERIENCE_TYPES[0])
        variants.append(wrong_distribution)
        narrow_types = valid_set()
        for case in narrow_types:
            replacement = evaluation_case(
                int(case["case_id"].split("-")[1]),
                case["expected_findings"][0]["verdict"],
                "API_DESIGN",
            )
            case.clear()
            case.update(replacement)
        variants.append(narrow_types)
        draft = valid_set()
        draft[0]["label_status"] = "DRAFT"
        variants.append(draft)

        for index, cases in enumerate(variants):
            with self.subTest(index=index):
                self.assertFalse(validate_evaluation_set(cases, self.policy)["valid"])

    def test_rejects_duplicate_case_ids_and_normalized_document_text(self):
        # Break caught: counting repeated cases or whitespace/case variants as independent evidence.
        duplicate_id = valid_set()
        duplicate_id[1]["case_id"] = duplicate_id[0]["case_id"]
        duplicate_text = valid_set()
        duplicate_text[1]["documents"][0]["text"] = (
            "  " + duplicate_text[0]["documents"][0]["text"].upper() + "  "
        )
        duplicate_text[1]["expected_findings"][0]["claim_quote"] = duplicate_text[1]["documents"][0]["text"]

        self.assertFalse(validate_evaluation_set(duplicate_id, self.policy)["valid"])
        self.assertFalse(validate_evaluation_set(duplicate_text, self.policy)["valid"])

    def test_cli_rejects_report_escape_before_reading_cases_or_writing(self):
        # Break caught: path traversal creating reports outside outputs/position-lora.
        target = Path("outputs/outside-position-eval.json").resolve()
        with self.assertRaisesRegex(ValueError, "report"):
            main(["--policy", "missing-policy.json", "--case", "missing-case.json", "--report", str(target)])
        self.assertFalse(target.exists())

    def test_cli_does_not_write_report_when_case_loading_fails(self):
        # Break caught: leaving a plausible review artifact after structural validation failed.
        report = Path("outputs/position-lora/task5-invalid-input-report.json").resolve()
        report.unlink(missing_ok=True)
        try:
            with self.assertRaises((ValueError, FileNotFoundError, json.JSONDecodeError)):
                main(["--policy", str(POLICY_PATH), "--case", "missing-case.json", "--report", str(report)])
            self.assertFalse(report.exists())
        finally:
            report.unlink(missing_ok=True)

    def test_cli_writes_count_only_review_report_for_invalid_draft_set(self):
        # Break caught: suppressing failed review evidence or leaking authored document text.
        report = Path("outputs/position-lora/task5-draft-review.json").resolve()
        report.unlink(missing_ok=True)
        try:
            exit_code = main(["--policy", str(POLICY_PATH), "--case", str(CASE_PATH), "--report", str(report)])
            payload = json.loads(report.read_text(encoding="utf-8"))
            serialized = json.dumps(payload, ensure_ascii=False)
        finally:
            report.unlink(missing_ok=True)

        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["valid"])
        self.assertNotIn("Redis를 활용해", serialized)


if __name__ == "__main__":
    unittest.main()

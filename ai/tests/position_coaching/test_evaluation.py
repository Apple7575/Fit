import copy
import json
import tempfile
import unittest
from pathlib import Path

from ai.position_coaching.evaluation import load_evaluation_case, score_evaluation
from ai.scripts.validate_position_eval_set import main, validate_evaluation_set


CASE_PATH = Path("ai/evals/position_coaching/cases-v2/draft/marketing-001.json")
POLICY_PATH = Path("ai/evals/position_coaching/evaluation-policy-v2.json")
VERDICTS = ("SUFFICIENT", "PARTIAL", "CLAIM_ONLY", "NOT_ASSESSABLE")
CLAIM_TYPES = (
    "PROBLEM_SOLVING", "ACHIEVEMENT", "DECISION", "EXECUTION",
    "COLLABORATION", "GROWTH", "OTHER",
)
REQUIRED = {
    "PROBLEM_SOLVING": ["PROBLEM", "ROLE", "ACTION", "REASONING", "VERIFICATION", "RESULT"],
    "ACHIEVEMENT": ["SITUATION", "ROLE", "ACTION", "VERIFICATION", "RESULT"],
    "DECISION": ["SITUATION", "ROLE", "ACTION", "REASONING", "RESULT"],
    "EXECUTION": ["SITUATION", "ROLE", "ACTION", "PROCESS", "RESULT"],
    "COLLABORATION": ["SITUATION", "ROLE", "ACTION", "PROCESS", "RESULT"],
    "GROWTH": ["SITUATION", "ACTION", "VERIFICATION", "LEARNING"],
    "OTHER": ["SITUATION", "ROLE", "ACTION", "RESULT"],
}


def evaluation_case(index, verdict, claim_type, position_name, *, status="DRAFT"):
    required = REQUIRED[claim_type]
    if verdict == "SUFFICIENT":
        present, missing = required, []
    elif verdict == "PARTIAL":
        present = ["ACTION"]
        missing = [element for element in required if element != "ACTION"]
    else:
        present, missing = [], required
    text = f"독립 평가 문서 {index} {verdict} {claim_type}"
    return {
        "schema_version": "2.0",
        "case_id": f"case-{index:03d}",
        "label_status": status,
        "rubric_id": "experience-depth-v1",
        "position_context": {
            "position_name": position_name,
            "priority_requirements": ["핵심 업무"],
        },
        "question": "이 경험을 구체적으로 설명해 주세요.",
        "documents": [{"document_id": "essay-1", "document_type": "SELF_INTRO", "text": text}],
        "expected_findings": [{
            "claim_type": claim_type,
            "claim_quote": text,
            "verdict": verdict,
            "present_elements": present,
            "missing_elements": missing,
        }],
        "forbidden_output_substrings": ["합격"],
    }


def valid_set():
    positions = ["백엔드", "프론트엔드", "데이터", "마케팅", "영업", "인사"]
    return [
        evaluation_case(
            index, VERDICTS[index // 3], CLAIM_TYPES[index % len(CLAIM_TYPES)],
            positions[index % len(positions)],
        )
        for index in range(12)
    ]


def actual_finding(case, finding_id="finding-1"):
    expected = case["expected_findings"][0]
    quote = expected["claim_quote"]
    start = case["documents"][0]["text"].index(quote)
    return {
        "finding_id": finding_id,
        "claim_type": expected["claim_type"],
        "claim": {"quote": quote, "document_id": "essay-1", "start_offset": start, "end_offset": start + len(quote)},
        "present_elements": [{"element": element, "quote": quote} for element in expected["present_elements"]],
        "missing_elements": expected["missing_elements"],
        "verdict": expected["verdict"],
        "reason": "독립 작성된 테스트 판단입니다.",
        "follow_up_questions": [],
    }


def valid_prediction(case, findings=None, response_text="safe response"):
    findings = [actual_finding(case)] if findings is None else findings
    return {
        "schema_valid": True,
        "output": {
            "analysis_status": "COMPLETED" if findings else "NO_EXPERIENCE_CLAIM",
            "rubric": {"id": "experience-depth-v1", "version": 1},
            "findings": findings,
            "model_metadata": {
                "base_model": "fixture-model", "base_revision": "fixture-revision",
                "adapter": None, "training_dataset": None, "prompt_version": "experience-depth-v1",
            },
        },
        "response_text": response_text,
    }


class EvaluationCaseLoadingTest(unittest.TestCase):
    def test_repository_case_uses_v2_universal_contract_and_remains_draft(self):
        case = load_evaluation_case(CASE_PATH)
        self.assertEqual(case["rubric_id"], "experience-depth-v1")
        self.assertEqual(case["position_context"]["position_name"], "마케팅 매니저")
        self.assertEqual(case["label_status"], "DRAFT")
        self.assertIn(case["expected_findings"][0]["claim_type"], CLAIM_TYPES)

    def test_refuses_to_score_draft_cases(self):
        case = load_evaluation_case(CASE_PATH)
        with self.assertRaisesRegex(ValueError, "HUMAN_APPROVED"):
            score_evaluation([case], {case["case_id"]: valid_prediction(case)})

    def test_loader_rejects_legacy_rubric_and_invalid_partition(self):
        base = evaluation_case(1, "PARTIAL", "ACHIEVEMENT", "마케팅")
        mutations = []
        legacy = copy.deepcopy(base)
        legacy["rubric_id"] = "backend-v1"
        mutations.append(legacy)
        invalid_partition = copy.deepcopy(base)
        invalid_partition["expected_findings"][0]["missing_elements"].append("LEARNING")
        mutations.append(invalid_partition)
        absent_quote = copy.deepcopy(base)
        absent_quote["expected_findings"][0]["claim_quote"] = "문서에 없는 근거"
        mutations.append(absent_quote)
        with tempfile.TemporaryDirectory() as directory:
            for index, payload in enumerate(mutations):
                with self.subTest(index=index):
                    path = Path(directory) / f"case-{index}.json"
                    path.write_text(json.dumps(payload), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_evaluation_case(path)


class EvaluationScoringTest(unittest.TestCase):
    def setUp(self):
        self.case = evaluation_case(1, "PARTIAL", "ACHIEVEMENT", "마케팅", status="HUMAN_APPROVED")

    def test_perfect_prediction_has_perfect_metrics(self):
        result = score_evaluation([self.case], {self.case["case_id"]: valid_prediction(self.case)})
        self.assertEqual(result["verdict_accuracy"]["rate"], 1.0)
        self.assertEqual(result["present_elements"]["f1"]["rate"], 1.0)
        self.assertEqual(result["missing_elements"]["f1"]["rate"], 1.0)

    def test_duplicate_actual_claim_type_and_quote_key_is_rejected(self):
        findings = [actual_finding(self.case, "one"), actual_finding(self.case, "two")]
        with self.assertRaisesRegex(ValueError, "duplicate.*finding key"):
            score_evaluation([self.case], {self.case["case_id"]: valid_prediction(self.case, findings)})

    def test_schema_failed_response_is_counted_without_text_leakage(self):
        secret = "민감한 경험 합격"
        prediction = {"schema_valid": False, "output": None, "response_text": secret}
        result = score_evaluation([self.case], {self.case["case_id"]: prediction})
        self.assertEqual(result["schema_valid_response_rate"]["rate"], 0.0)
        self.assertEqual(result["forbidden_output_occurrence_count"], 1)
        self.assertNotIn(secret, json.dumps(result, ensure_ascii=False))


class EvaluationSetValidationTest(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

    def test_accepts_twelve_draft_cases_across_positions_and_claim_types(self):
        report = validate_evaluation_set(valid_set(), self.policy)
        self.assertTrue(report["valid"])
        self.assertEqual(report["case_count"], 12)
        self.assertEqual(report["count_by_verdict"], {verdict: 3 for verdict in VERDICTS})
        self.assertEqual(report["position_name_count"], 6)
        self.assertEqual(report["claim_type_count"], 7)

    def test_policy_is_fixed_to_v2_draft_regression_contract(self):
        self.assertEqual(self.policy, {
            "schema_version": "2.0", "rubric_id": "experience-depth-v1",
            "required_case_count": 12,
            "required_count_by_verdict": {verdict: 3 for verdict in VERDICTS},
            "minimum_position_names": 6, "minimum_claim_types": 6,
            "required_label_status": "DRAFT",
        })
        weakened = copy.deepcopy(self.policy)
        weakened["required_case_count"] = 4
        with self.assertRaises(ValueError):
            validate_evaluation_set([], weakened)

    def test_rejects_narrow_position_or_claim_type_coverage(self):
        narrow_positions = valid_set()
        for case in narrow_positions:
            case["position_context"]["position_name"] = "백엔드"
        narrow_claims = [
            evaluation_case(index, VERDICTS[index // 3], "ACHIEVEMENT", f"직무 {index % 6}")
            for index in range(12)
        ]
        self.assertFalse(validate_evaluation_set(narrow_positions, self.policy)["valid"])
        self.assertFalse(validate_evaluation_set(narrow_claims, self.policy)["valid"])

    def test_cli_writes_valid_count_only_report_for_repository_fixtures(self):
        cases = sorted(CASE_PATH.parent.glob("*.json"))
        report = Path("outputs/position-lora/generalization-v2-test.json").resolve()
        report.unlink(missing_ok=True)
        argv = ["--policy", str(POLICY_PATH)]
        for case in cases:
            argv.extend(["--case", str(case)])
        argv.extend(["--report", str(report)])
        try:
            exit_code = main(argv)
            payload = json.loads(report.read_text(encoding="utf-8"))
        finally:
            report.unlink(missing_ok=True)
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["case_count"], 12)


if __name__ == "__main__":
    unittest.main()

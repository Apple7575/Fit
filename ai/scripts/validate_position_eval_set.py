from __future__ import annotations

import argparse
import json
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Any

from ai.position_coaching.contracts import VERDICTS
from ai.position_coaching.evaluation import (
    load_evaluation_case,
    validate_evaluation_case,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REPORT_ROOT = (REPOSITORY_ROOT / "outputs" / "position-lora").resolve()
CANONICAL_EVALUATION_POLICY_V1 = MappingProxyType(
    {
        "schema_version": "1.0",
        "profile_id": "backend-v1",
        "required_case_count": 60,
        "required_count_by_verdict": MappingProxyType(
            {
                "SUFFICIENT": 15,
                "PARTIAL": 15,
                "CLAIM_ONLY": 15,
                "NOT_ASSESSABLE": 15,
            }
        ),
        "minimum_experience_types": 6,
        "required_label_status": "HUMAN_APPROVED",
    }
)


def validate_evaluation_set(
    cases: Sequence[Mapping[str, Any]], policy: Mapping[str, Any]
) -> dict[str, Any]:
    """Return a count-only review report for a structurally valid candidate set."""
    validated_policy = _validate_policy(policy)
    if isinstance(cases, (str, bytes)) or not isinstance(cases, Sequence):
        raise ValueError("cases must be a sequence")
    validated_cases = [validate_evaluation_case(case) for case in cases]

    case_ids = [case["case_id"] for case in validated_cases]
    normalized_documents = [
        _normalize_document_text(document["text"])
        for case in validated_cases
        for document in case["documents"]
    ]
    statuses = Counter(case["label_status"] for case in validated_cases)
    profiles = Counter(case["position_profile_id"] for case in validated_cases)
    count_by_verdict: Counter[str] = Counter()
    experience_types: set[str] = set()
    single_finding_cases = 0
    for case in validated_cases:
        findings = case["expected_findings"]
        if len(findings) == 1:
            single_finding_cases += 1
            count_by_verdict[findings[0]["verdict"]] += 1
        experience_types.update(finding["experience_type"] for finding in findings)

    issues: list[str] = []
    if len(validated_cases) != validated_policy["required_case_count"]:
        issues.append("CASE_COUNT_MISMATCH")
    if len(case_ids) != len(set(case_ids)):
        issues.append("DUPLICATE_CASE_ID")
    if len(normalized_documents) != len(set(normalized_documents)):
        issues.append("DUPLICATE_NORMALIZED_DOCUMENT_TEXT")
    if single_finding_cases != len(validated_cases):
        issues.append("CASE_MUST_HAVE_EXACTLY_ONE_EXPECTED_FINDING")
    if dict(count_by_verdict) != validated_policy["required_count_by_verdict"]:
        issues.append("VERDICT_DISTRIBUTION_MISMATCH")
    if len(experience_types) < validated_policy["minimum_experience_types"]:
        issues.append("INSUFFICIENT_EXPERIENCE_TYPE_COVERAGE")
    if statuses != Counter(
        {validated_policy["required_label_status"]: len(validated_cases)}
    ):
        issues.append("LABEL_STATUS_MISMATCH")
    if profiles != Counter({validated_policy["profile_id"]: len(validated_cases)}):
        issues.append("PROFILE_MISMATCH")

    return {
        "schema_version": "1.0",
        "valid": not issues,
        "case_count": len(validated_cases),
        "duplicate_case_id_count": len(case_ids) - len(set(case_ids)),
        "duplicate_normalized_document_text_count": (
            len(normalized_documents) - len(set(normalized_documents))
        ),
        "single_finding_case_count": single_finding_cases,
        "count_by_verdict": {
            verdict: count_by_verdict.get(verdict, 0) for verdict in sorted(VERDICTS)
        },
        "experience_type_count": len(experience_types),
        "count_by_label_status": dict(sorted(statuses.items())),
        "issues": issues,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a human-approved position evaluation set.")
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--case", required=True, action="append", dest="cases", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args(argv)

    report_path = _validated_report_path(args.report)
    policy_payload = json.loads(args.policy.read_text(encoding="utf-8"))
    cases = [load_evaluation_case(path) for path in args.cases]
    report = validate_evaluation_set(cases, policy_payload)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0 if report["valid"] else 1


def _validate_policy(policy: Any) -> dict[str, Any]:
    if (
        not isinstance(policy, Mapping)
        or set(policy) != set(CANONICAL_EVALUATION_POLICY_V1)
    ):
        raise ValueError("policy must contain exactly the required fields")
    required_case_count = policy["required_case_count"]
    minimum_types = policy["minimum_experience_types"]
    if type(required_case_count) is not int:
        raise ValueError("required_case_count must be an integer")
    if type(minimum_types) is not int:
        raise ValueError("minimum_experience_types must be an integer")
    distribution = policy["required_count_by_verdict"]
    if not isinstance(distribution, Mapping) or set(distribution) != VERDICTS:
        raise ValueError("required_count_by_verdict must cover every verdict")
    if any(type(count) is not int for count in distribution.values()):
        raise ValueError("verdict counts must be integers")

    normalized = {
        "schema_version": policy["schema_version"],
        "profile_id": policy["profile_id"],
        "required_case_count": required_case_count,
        "required_count_by_verdict": dict(distribution),
        "minimum_experience_types": minimum_types,
        "required_label_status": policy["required_label_status"],
    }
    canonical = {
        **CANONICAL_EVALUATION_POLICY_V1,
        "required_count_by_verdict": dict(
            CANONICAL_EVALUATION_POLICY_V1["required_count_by_verdict"]
        ),
    }
    if normalized != canonical:
        raise ValueError("policy must match canonical evaluation-policy-v1")
    return normalized


def _normalize_document_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _validated_report_path(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(REPORT_ROOT) or resolved.suffix.lower() != ".json":
        raise ValueError("report must be a JSON file inside outputs/position-lora")
    return resolved


if __name__ == "__main__":
    raise SystemExit(main())

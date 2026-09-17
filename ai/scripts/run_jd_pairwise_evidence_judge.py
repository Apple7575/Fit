from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from ai.jd_coaching.baseline import call_qwen, load_qwen_config, score_connections
from ai.jd_coaching.evaluation import evaluate_connection_predictions
from ai.jd_coaching.judge import (
    build_judge_messages,
    derive_labels,
    judge_output_schema,
    select_connection_cases,
    select_relevant_document_sections,
    validate_judge_output,
)


AI_ROOT = Path(__file__).parents[1]
DEFAULT_CASE = (
    AI_ROOT
    / "evals"
    / "jd_coaching"
    / "cases"
    / "samsung-ds-global-manufacturing-sw-intern-holdout-001.json"
)
DEFAULT_DOCUMENT = (
    AI_ROOT
    / "evals"
    / "jd_coaching"
    / "sources"
    / "samsung-ds-global-manufacturing-sw-intern-2026.json"
)
DEFAULT_POLICY = (
    AI_ROOT / "evals" / "jd_coaching" / "connection-policy-v1.json"
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_result(path: Path, result: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="전체 JD를 유지하고 연결 조합을 한 건씩 Qwen으로 판정한다."
    )
    parser.add_argument("--case", type=Path, default=DEFAULT_CASE)
    parser.add_argument("--document", type=Path, default=DEFAULT_DOCUMENT)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--env-file", type=Path, default=AI_ROOT / ".env")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--reference-label", default="PARTIALLY_SUPPORTED"
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="모델 계약 실패를 기록하고 다음 연결 평가를 계속한다.",
    )
    parser.add_argument(
        "--document-scope",
        choices=("full", "relevant-sections"),
        default="full",
    )
    parser.add_argument("--max-tokens", type=int, default=1600)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="기존 체크포인트의 완료 항목 다음부터 재개한다.",
    )
    args = parser.parse_args()

    case = load_json(args.case)
    document = load_json(args.document)
    policy = load_json(args.policy)
    config = load_qwen_config(args.env_file)
    selected_label = (
        None if args.reference_label.upper() == "ALL" else args.reference_label
    )
    selected_cases = select_connection_cases(
        case, reference_label=selected_label
    )
    if not selected_cases:
        raise ValueError(
            f"선택한 reference label이 없다: {args.reference_label}"
        )

    result = {
        "run_type": "PAIRWISE_REQUIRED_EVIDENCE_JUDGE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "case_id": case["case_id"],
        "document_id": document["document_id"],
        "evaluation_context": case.get("evaluation_context"),
        "reference_label": args.reference_label.upper(),
        "input_control": {
            "jd_document": (
                "FULL_DOCUMENT_UNCHANGED"
                if args.document_scope == "full"
                else "ROLE_REFERENCED_SECTIONS_ONLY"
            ),
            "connections_per_call": 1,
        },
        "run_status": "RUNNING",
        "official_metric_eligible": case.get("label_status") == "HUMAN_APPROVED",
        "results": [],
        "failures": [],
    }
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    if args.resume and args.output.exists():
        checkpoint = load_json(args.output)
        if checkpoint.get("case_id") != case["case_id"]:
            raise ValueError("checkpoint case_id does not match requested case")
        result = checkpoint
        result["run_status"] = "RUNNING"
        if result.pop("failure", None) is not None:
            result["completed"] = len(result["results"])
        result.pop("metrics", None)
        result.pop("evidence_metrics", None)
        result.pop("scores", None)
        usage = {
            key: int(result.get("usage", {}).get(key, 0) or 0)
            for key in usage
        }

    result.setdefault("failures", [])
    completed_count = int(result.get("completed", len(result["results"])))

    for index, selected_case in enumerate(
        selected_cases[completed_count:], start=completed_count + 1
    ):
        connection = selected_case["expected_connections"][0]
        selected_document = (
            document
            if args.document_scope == "full"
            else select_relevant_document_sections(document, selected_case)
        )
        response = None
        for attempt in range(2):
            try:
                response = call_qwen(
                    config,
                    build_judge_messages(selected_document, selected_case, policy),
                    max_tokens=args.max_tokens,
                    schema=judge_output_schema(),
                    schema_name="jd_pairwise_evidence_judge_output",
                )
                for key in usage:
                    usage[key] += int(response["usage"].get(key, 0) or 0)
                validate_judge_output(response["output"], selected_case)
                derived = derive_labels(response["output"], selected_case)[0]
                break
            except Exception as error:
                if attempt == 0:
                    continue
                result["run_status"] = "FAILED"
                result["failure"] = {
                    "index": index,
                    "role_element_id": connection["role_element_id"],
                    "experience_id": connection["experience_id"],
                    "error_type": type(error).__name__,
                    "message": str(error),
                    "model_output": response.get("output") if response else None,
                }
                result["usage"] = usage
                result["completed"] = index
                if args.continue_on_error:
                    result["failures"].append(result.pop("failure"))
                    result["run_status"] = "RUNNING"
                    save_result(args.output, result)
                    break
                save_result(args.output, result)
                raise
        else:
            raise RuntimeError("unreachable retry state")

        if len(result["results"]) + len(result["failures"]) == index:
            if result["failures"] and result["failures"][-1]["index"] == index:
                print(
                    f"[{index}/{len(selected_cases)}] "
                    f"{connection['role_element_id']} x {connection['experience_id']} "
                    "=> FAILED"
                )
                continue

        result["results"].append(
            {
                "index": index,
                "role_element_id": connection["role_element_id"],
                "experience_id": connection["experience_id"],
                "reference_label": connection["label"],
                "predicted_label": derived["derived_label"],
                "correct": connection["label"] == derived["derived_label"],
                "derived_connection": derived,
                "judge_output": response["output"],
                "usage": response["usage"],
            }
        )
        result["completed"] = index
        result["usage"] = usage
        save_result(args.output, result)
        print(
            f"[{index}/{len(selected_cases)}] "
            f"{connection['role_element_id']} x {connection['experience_id']} "
            f"=> {derived['derived_label']}"
        )

    correct = sum(item["correct"] for item in result["results"])
    total = len(selected_cases)
    result["run_status"] = (
        "COMPLETED_WITH_FAILURES" if result["failures"] else "COMPLETED"
    )
    result["metrics"] = {
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total, 4),
        "reference_label_recall": round(correct / total, 4),
        "average_tokens_per_connection": round(usage["total_tokens"] / total, 2),
    }
    predictions = [
        {
            **item["derived_connection"],
            "label": item["predicted_label"],
        }
        for item in result["results"]
    ]
    selected_reference = [
        item["expected_connections"][0] for item in selected_cases
    ]
    result["evidence_metrics"] = evaluate_connection_predictions(
        selected_reference,
        predictions,
        {
            experience["experience_id"]: experience["text"]
            for experience in case["experiences"]
        },
    )
    if (
        selected_label is None
        and result["official_metric_eligible"]
        and not result["failures"]
    ):
        result["scores"] = score_connections(
            {
                "connections": [
                    {
                        "role_element_id": item["role_element_id"],
                        "experience_id": item["experience_id"],
                        "label": item["predicted_label"],
                    }
                    for item in result["results"]
                ]
            },
            case,
        )
    elif selected_label is None and not result["official_metric_eligible"]:
        result["metric_note"] = (
            "DRAFT 라벨 비교 결과이며 사람이 확정하기 전에는 공식 성능으로 사용하지 않는다."
        )
    elif result["failures"]:
        result["metric_note"] = (
            "계약 실패 연결은 오답으로 포함했고 scores 대신 evidence_metrics를 사용한다."
        )
    save_result(args.output, result)
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))
    print(f"result={args.output.resolve()}")


if __name__ == "__main__":
    main()

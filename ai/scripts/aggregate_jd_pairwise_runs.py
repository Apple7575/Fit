from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai.jd_coaching.evaluation import evaluate_connection_predictions


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="완료된 JD pairwise 평가 실행을 하나의 지표로 합친다."
    )
    parser.add_argument("--run", type=Path, action="append", required=True)
    parser.add_argument("--case-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    cases = {
        case["case_id"]: case
        for case in (
            load_json(path) for path in sorted(args.case_dir.glob("*.json"))
        )
    }
    gold = []
    predictions = []
    experience_text_by_id = {}
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    run_summaries = []

    for path in args.run:
        run = load_json(path)
        if run.get("run_status") not in {"COMPLETED", "COMPLETED_WITH_FAILURES"}:
            raise ValueError(f"completed run required: {path}")
        if not run.get("official_metric_eligible"):
            raise ValueError(f"human-approved run required: {path}")
        case = cases[run["case_id"]]
        expected_by_pair = {
            (item["role_element_id"], item["experience_id"]): item
            for item in case["expected_connections"]
        }
        if run.get("reference_label") != "ALL":
            raise ValueError(f"ALL-label run required: {path}")
        gold.extend(case["expected_connections"])
        for item in run["results"]:
            pair = (item["role_element_id"], item["experience_id"])
            _ = expected_by_pair[pair]
            predictions.append(
                {
                    **item["derived_connection"],
                    "label": item["predicted_label"],
                }
            )
        experience_text_by_id.update(
            {
                item["experience_id"]: item["text"]
                for item in case["experiences"]
            }
        )
        for key in usage:
            usage[key] += int(run.get("usage", {}).get(key, 0) or 0)
        run_summaries.append(
            {
                "case_id": run["case_id"],
                "connections": len(run["results"]),
                "correct": sum(item["correct"] for item in run["results"]),
                "failures": len(run.get("failures", [])),
            }
        )

    result = {
        "run_type": "AGGREGATED_PAIRWISE_REQUIRED_EVIDENCE_JUDGE",
        "runs": run_summaries,
        "metrics": evaluate_connection_predictions(
            gold, predictions, experience_text_by_id
        ),
        "usage": usage,
        "average_tokens_per_connection": (
            usage["total_tokens"] / len(gold) if gold else 0.0
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

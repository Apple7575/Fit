from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai.jd_coaching.evaluation import summarize_evaluation_cases


AI_ROOT = Path(__file__).parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="JD 연결 평가셋의 확정·초안 라벨 수를 분리해 집계한다."
    )
    parser.add_argument(
        "--case-dir",
        type=Path,
        default=AI_ROOT / "evals" / "jd_coaching" / "cases",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    cases = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(args.case_dir.glob("*.json"))
    ]
    summary = summarize_evaluation_cases(cases)
    rendered = json.dumps(summary, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

"""전체 코퍼스 집계에서 재현 가능한 청킹 실험 기업 표본을 만든다."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.rag_corpus.experiment_selection import select_companies  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="기업 RAG 청킹 실험 표본 선택")
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--size", type=int, default=100)
    parser.add_argument("--holdout-size", type=int, default=20)
    args = parser.parse_args()

    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    companies = select_companies(
        summary["companies"], size=args.size, holdout_size=args.holdout_size,
    )
    payload = {
        "selection_version": "representative-100-v1",
        "source_summary": str(args.summary.resolve()),
        "company_count": len(companies),
        "groups": dict(sorted(Counter(item["group"] for item in companies).items())),
        "companies": companies,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps({
        "status": "success", "output": str(args.output),
        "company_count": len(companies), "groups": payload["groups"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

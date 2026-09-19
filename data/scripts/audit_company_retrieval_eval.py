"""기존 실버 평가셋을 수정하지 않고 근거 위험을 재판정한다."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.rag_corpus.evaluation_audit import audit_case  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="기업 검색 평가셋 보수적 근거 감사")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.input.resolve() == args.output.resolve():
        parser.error("입력과 출력 경로는 달라야 합니다")

    cases = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line]
    results = [audit_case(case) for case in cases]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(result, ensure_ascii=False) + "\n" for result in results), encoding="utf-8",
    )
    summary = {
        "input": str(args.input.resolve()), "total": len(results),
        "status_counts": dict(Counter(result["audit_status"] for result in results)),
        "reason_counts": dict(Counter(reason for result in results for reason in result["reasons"])),
    }
    args.output.with_suffix(args.output.suffix + ".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

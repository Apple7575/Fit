"""DART 원문에서 기업 검색 평가셋 초안을 생성한다."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.rag_corpus.evaluation_dataset import extract_source_units  # noqa: E402
from pipeline.rag_corpus.evaluation_generation import generate_cases, select_parseable_report  # noqa: E402
from pipeline.rag_corpus.evaluation_llm import (  # noqa: E402
    GENERATOR_PROMPT_VERSION, JUDGE_PROMPT_VERSION, QwenEvaluationClient,
)
from pipeline.raw_sources.dart_archive import DartArchive  # noqa: E402


CATEGORIES = (
    "BUSINESS", "PERFORMANCE", "TECHNOLOGY_RND", "INVESTMENT_STRATEGY", "DISCLOSED_RISKS",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="사업보고서 원본 기반 검색 평가셋 생성")
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--dart-archive", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--group", choices=("tuning", "holdout", "all"), default="tuning")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("--limit는 1 이상이어야 합니다")
    cutoff = date.fromisoformat(args.as_of)
    selection_bytes = args.selection.read_bytes()
    selection = json.loads(selection_bytes)
    companies = [item for item in selection["companies"] if args.group == "all" or item["group"] == args.group]
    companies = companies[:args.limit]
    if not companies:
        parser.error("선택된 기업이 없습니다")
    env = dict(dotenv_values(args.env_file)) if args.env_file else {}
    base_url = env.get("QWEN_BASE_URL") or os.environ.get("QWEN_BASE_URL")
    model = env.get("QWEN_MODEL") or os.environ.get("QWEN_MODEL")
    key = env.get("QWEN_API_KEY") or os.environ.get("QWEN_API_KEY")
    if not all((base_url, model, key)):
        parser.error("QWEN_BASE_URL, QWEN_MODEL, QWEN_API_KEY가 필요합니다")
    client = QwenEvaluationClient(base_url, model, key)
    manifest = {
        "selection_sha256": sha256(selection_bytes).hexdigest(), "archive": str(args.dart_archive.resolve()),
        "as_of": cutoff.isoformat(), "group": args.group, "limit": args.limit,
        "model": model, "generator_prompt_version": GENERATOR_PROMPT_VERSION,
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "source_selection_version": "numeric-entity-v9",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output.with_suffix(args.output.suffix + ".manifest.json")
    if manifest_path.exists():
        if json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
            raise ValueError("기존 출력의 설정이 다릅니다. 다른 출력 경로를 지정하세요")
    elif args.output.exists():
        raise ValueError("manifest 없는 기존 출력은 재개할 수 없습니다")
    else:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    coverage_path = args.output.with_suffix(args.output.suffix + ".coverage.jsonl")
    completed = set()
    coverage_records: dict[str, dict[str, object]] = {}
    if coverage_path.exists():
        for line in coverage_path.read_text(encoding="utf-8").splitlines():
            if line:
                record = json.loads(line)
                coverage_records[record["corp_code"]] = record
                completed.add(record["corp_code"])
    existing_categories: dict[str, set[str]] = {}
    if args.output.exists():
        for line in args.output.read_text(encoding="utf-8").splitlines():
            if line:
                case = json.loads(line)
                existing_categories.setdefault(case["corp_code"], set()).add(case["category"])
    for corp_code, categories in existing_categories.items():
        if corp_code not in completed:
            record = {"corp_code": corp_code, "missing_categories": {
                category: "NO_GROUNDED_CANDIDATE" for category in CATEGORIES if category not in categories
            }}
            with coverage_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            coverage_records[corp_code] = record
            completed.add(corp_code)
    failures: list[dict[str, str]] = []
    with DartArchive(args.dart_archive) as archive:
        for company in companies:
            corp_code = company["corp_code"]
            if corp_code in completed:
                continue
            try:
                ref, document, skipped_reports = select_parseable_report(
                    archive, corp_code, as_of=cutoff.isoformat(),
                )
                units = extract_source_units(document)
                cases = generate_cases(
                    units, corp_code=corp_code, rcept_no=ref.rcept_no,
                    published_at=date.fromisoformat(f"{ref.rcept_dt[:4]}-{ref.rcept_dt[4:6]}-{ref.rcept_dt[6:]}").isoformat(),
                    categories=CATEGORIES, generate=client.generate, judge=client.judge,
                )
                for case in cases:
                    case["company_name"] = ref.corp_name
                    case["group"] = company["group"]
                    case["selection_version"] = selection["selection_version"]
                    case["source_report_year"] = ref.year
                    case["source_status"] = "FALLBACK_PRIOR_REPORT" if skipped_reports else "LATEST_REPORT"
                    case["skipped_reports"] = skipped_reports
                with args.output.open("a", encoding="utf-8") as stream:
                    for case in cases:
                        stream.write(json.dumps(case, ensure_ascii=False) + "\n")
                coverage = {"corp_code": corp_code, "rcept_no": ref.rcept_no,
                            "missing_categories": {category: "NO_GROUNDED_CANDIDATE"
                                                   for category in CATEGORIES
                                                   if category not in {case["category"] for case in cases}}}
                with coverage_path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(coverage, ensure_ascii=False) + "\n")
                coverage_records[corp_code] = coverage
                completed.add(corp_code)
                print(json.dumps({"corp_code": corp_code, "cases": len(cases),
                                  "validated": sum(c["validation_status"] == "AUTO_VALIDATED" for c in cases)},
                                 ensure_ascii=False), flush=True)
            except Exception as error:
                failures.append({"corp_code": corp_code, "error_type": type(error).__name__, "message": str(error)})
                print(json.dumps(failures[-1], ensure_ascii=False), file=sys.stderr, flush=True)
    counts = Counter(json.loads(line)["validation_status"] for line in args.output.read_text(encoding="utf-8").splitlines()) if args.output.exists() else Counter()
    missing_counts = Counter(category for record in coverage_records.values()
                             for category in record["missing_categories"])
    summary = {"requested_companies": len(companies), "completed_companies": len(completed),
               "status_counts": dict(counts), "missing_categories": dict(missing_counts),
               "failures": failures}
    args.output.with_suffix(args.output.suffix + ".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

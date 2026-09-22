"""검색 평가 문항의 사람 검토 초안을 만든다.

평가 결과 JSON(`ai/evals/company_analysis/results/*.json`)의 LLM 생성 검색 문항을 모아, 문항마다
① 원래 문단(정답) 발췌 ② 같은 기업 안 BM25 상위 후보 발췌를 붙여 번호 목록 Markdown 과 JSONL 초안을 쓴다.
사람은 Markdown 을 읽고 문항별로 유지·수정·삭제와 추가 정답 문단을 정하고, 확정된 줄만 `status: GOLD` 로 골드 파일에 남긴다.

    python -m ai.scripts.build_retrieval_review --results ai/evals/company_analysis/results --out ai/evals/company_analysis/gold

GPU 가 필요 없다(BM25 만 쓴다). 청크 DB 접속은 COMPANY_ANALYSIS_RAG_DATABASE_URL 을 쓴다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ai.company_analysis.api import build_business_reports  # noqa: E402
from ai.company_analysis.retrieval import BM25Index  # noqa: E402

EXCERPT = 220
CANDIDATES = 3


def _excerpt(text: str, n: int = EXCERPT) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= n else flat[:n] + "…"


def collect_questions(results_dir: Path) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for path in sorted(results_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data.get("retrieval", []):
            key = (item["corp_code"], item["question"])
            if key in seen:
                continue
            seen.add(key)
            rows.append({**item, "result_file": path.name})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", type=Path, default=Path("ai/evals/company_analysis/results"))
    parser.add_argument("--out", type=Path, default=Path("ai/evals/company_analysis/gold"))
    parser.add_argument("--name", default="retrieval-review-draft")
    args = parser.parse_args()

    questions = collect_questions(args.results)
    reports = build_business_reports()
    args.out.mkdir(parents=True, exist_ok=True)

    cache: dict[str, tuple] = {}
    md = ["# 검색 문항 검토 초안", "", f"문항 {len(questions)}개. 각 문항의 `정답` 은 질문을 만든 원래 문단, `후보` 는 같은 기업 안 BM25 상위 {CANDIDATES}건이다.",
          "검토자는 문항별로 **유지 / 수정 / 삭제** 와 추가 정답 문단(후보 번호)을 정한다. 초안 판정은 기계 규칙이 아니라 검토 보조용이다.", ""]
    jsonl: list[str] = []
    for number, item in enumerate(questions, start=1):
        corp = item["corp_code"]
        if corp not in cache:
            report = reports.latest(corp)
            cache[corp] = (report, BM25Index(report.chunks) if report else None, report.by_id() if report else {})
            print(f"[{corp}] chunks={len(report.chunks) if report else 0}", file=sys.stderr)
        report, bm25, by_id = cache[corp]
        original = by_id.get(item["evidence_id"])
        hits = bm25.search(item["question"], top_k=CANDIDATES + 1) if bm25 else []
        candidates = [h.chunk for h in hits if h.chunk.evidence_id != item["evidence_id"]][:CANDIDATES]
        md += [f"## {number}. [{corp}] {item['question']}", "",
               f"- 원래 절: {item['section_title']} · 이전 하이브리드 순위: {item['ranks'].get('hybrid')}",
               f"- 정답 `{item['evidence_id'][-12:]}`: {_excerpt(original.content) if original else '(현재 청크에 없음)'}"]
        for k, chunk in enumerate(candidates, start=1):
            md.append(f"- 후보{k} `{chunk.evidence_id[-12:]}` ({chunk.section_title}{' · 표' if chunk.is_table else ''}): {_excerpt(chunk.content)}")
        md += ["- 초안 판정: ", "- 검토 결정: ", ""]
        jsonl.append(json.dumps({
            "no": number, "corp_code": corp, "question": item["question"], "evidence_id": item["evidence_id"],
            "section_title": item["section_title"], "accepted_evidence_ids": [item["evidence_id"]],
            "candidates": [c.evidence_id for c in candidates], "status": "REVIEW", "note": "",
        }, ensure_ascii=False))

    (args.out / f"{args.name}.md").write_text("\n".join(md), encoding="utf-8")
    (args.out / f"{args.name}.jsonl").write_text("\n".join(jsonl) + "\n", encoding="utf-8")
    print(f"saved: {args.out / args.name}.md / .jsonl ({len(questions)} questions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

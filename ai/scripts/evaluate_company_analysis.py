"""기업 분석 담당의 첫 자동 평가 두 가지.

1. 숫자 질문 정확도 — DB 확정 지표(company_metric)로 질문·정답을 자동 생성해 채팅에 묻고 채점한다.
   사람이 만든 정답이 아니라 DB 값이 정답이므로 지금 바로 돌릴 수 있는 가장 확실한 지표다.
2. 검색 Recall@k — 사업보고서 서술 문단마다 Qwen 이 자연어 질문을 만들고, 그 질문으로 검색했을 때
   원래 문단이 상위 k 에 들어오는지 본다. BM25 / 벡터 / 하이브리드를 같은 질문으로 비교한다.

    python -m ai.scripts.evaluate_company_analysis --corp-code 00164779 --corp-code 01350869 --out outputs/company-analysis-eval

환경변수는 ai/company_analysis/api.py 와 같다(COMPANY_ANALYSIS_DATABASE_URL 등). GPU 서버와 DB 가 있어야 한다.
결과는 JSON(원본)과 Markdown(요약)으로 저장한다. 생성된 질문은 사람이 검토해 골드 정답셋의 씨앗으로 쓴다.

`--gold <jsonl>` 을 주면 검색 문항을 새로 만들지 않고 그 파일의 확정 문항을 쓴다. 한 줄이 한 문항이고
`accepted_evidence_ids` 에 정답으로 인정하는 문단 ID 를 여러 개 둘 수 있다("주력 제품이 뭐야" 처럼 여러 문단이
답인 질문). 순위는 그중 가장 먼저 나온 문단의 순위다. 골드 문항은 GPU 없이(BM25 만) 도 평가할 수 있다.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ai.company_analysis.api import get_company_chat_service  # noqa: E402
from ai.company_analysis.deterministic import money_unit, pct, scale  # noqa: E402
from ai.company_analysis.metric_answer import money_values_in  # noqa: E402
from ai.company_analysis.facts import (  # noqa: E402
    EMPLOYEE_COUNT,
    NET_INCOME,
    OPERATING_PROFIT,
    REVENUE,
    TOTAL_EQUITY,
    TOTAL_LIABILITIES,
    CompanyFacts,
)
from ai.company_analysis.retrieval import BM25Index, CompanyRetriever, VectorIndex  # noqa: E402

NARRATIVE_SECTIONS = re.compile(r"사업의 개요|주요 제품|기타 참고사항|재무상태 및 영업실적|영업의 현황|유동성|원재료|매출 및 수주|연구개발")
QUESTION_SCHEMA = {
    "type": "object",
    "properties": {"question": {"type": "string"}},
    "required": ["question"],
    "additionalProperties": False,
}
QUESTION_PROMPT = (
    "아래 문단은 한 기업의 사업보고서 일부다. 이 문단만 읽으면 답할 수 있는, 취업 준비생이 그 기업에 대해 물을 법한 "
    "자연스러운 한국어 질문을 하나 만든다. 문단의 문장을 그대로 베끼지 말고 일상 말투로 바꿔 쓴다. "
    "기업명은 '이 회사'로 쓰고, 질문은 60자 이내로 한다."
)


# --- 숫자 질문 -----------------------------------------------------------------------------------


@dataclass
class FactCase:
    corp_code: str
    corp_name: str
    metric: str
    question: str
    kind: str  # money | count | pct
    expected_value: float  # money 는 원, count 는 명, pct 는 %
    expected_tokens: list[str]  # 사람이 읽기 위한 기대 표기
    answer: str = ""
    verdict: str = ""  # correct | abstain | wrong | error
    latency_s: float = 0.0
    citations: int = 0


def _close(found: float, expected: float, tolerance: float) -> bool:
    return expected != 0 and abs(found - expected) / abs(expected) <= tolerance


def judge(answer: str, kind: str, expected_value: float, expected_tokens: list[str]) -> str:
    """값 기준 채점. 97.1조원·97조 1,468억원·97,146,675백만원 은 모두 같은 값으로 본다(0.5% 이내)."""
    if "근거를 찾지 못했습니다" in answer or not answer.strip():
        return "abstain"
    plain = answer.replace(" ", "")
    if any(token.replace(" ", "") in plain for token in expected_tokens):
        return "correct"
    if kind == "money":
        return "correct" if any(_close(v, expected_value, 0.005) for v in money_values_in(answer)) else "wrong"
    if kind == "count":
        numbers = [float(n.replace(",", "")) for n in re.findall(r"\d{1,3}(?:,\d{3})+|\d+", answer)]
        return "correct" if any(_close(n, expected_value, 0.0005) for n in numbers) else "wrong"
    numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?(?=\s*%)", answer)]
    return "correct" if any(abs(n - expected_value) <= 0.15 for n in numbers) else "wrong"


def fact_cases(facts: CompanyFacts) -> list[FactCase]:
    year = facts.latest_year()
    if year is None:
        return []
    unit, divisor = money_unit(facts)
    name = facts.profile.corp_name
    code = facts.profile.corp_code
    cases: list[FactCase] = []
    m = facts.metric

    def money(metric: str, label: str) -> None:
        value = m(year, metric)
        if value is not None:
            cases.append(FactCase(code, name, metric, f"{name}의 {year}년 {label}은 얼마야?", "money", value, [f"{scale(value, divisor)}{unit}"]))

    money(REVENUE, "매출액")
    money(OPERATING_PROFIT, "영업이익")
    money(NET_INCOME, "당기순이익")
    employees = m(year, EMPLOYEE_COUNT)
    if employees is not None:
        cases.append(FactCase(code, name, EMPLOYEE_COUNT, f"{name} 직원 수는 {year}년 기준 몇 명이야?", "count", float(employees), [f"{int(employees):,}명"]))
    op_margin = pct(m(year, OPERATING_PROFIT), m(year, REVENUE))
    if op_margin is not None:
        cases.append(FactCase(code, name, "operating_margin", f"{name}의 {year}년 영업이익률은?", "pct", op_margin, [f"{op_margin}%"]))
    debt = pct(m(year, TOTAL_LIABILITIES), m(year, TOTAL_EQUITY))
    if debt is not None:
        cases.append(FactCase(code, name, "debt_ratio", f"{name}의 {year}년 부채비율은 어느 정도야?", "pct", debt, [f"{debt}%"]))
    return cases


# --- 검색 -------------------------------------------------------------------------------------------


@dataclass
class RetrievalCase:
    corp_code: str
    evidence_id: str  # 대표 정답 문단(문항을 만든 원래 문단)
    section_title: str
    question: str
    ranks: dict[str, int | None] = field(default_factory=dict)  # method → 정답 문단 중 최상위 순위(1부터), 없으면 None
    accepted_evidence_ids: list[str] = field(default_factory=list)  # 정답으로 인정하는 문단 전부(대표 포함)
    source: str = "generated"  # generated | gold

    def accepted(self) -> set[str]:
        return {self.evidence_id, *self.accepted_evidence_ids}


def sample_chunks(report, k: int, rng: random.Random):
    pool = [c for c in report.chunks if not c.is_table and len(c.content) >= 200 and NARRATIVE_SECTIONS.search(c.section_title)]
    if len(pool) < k:
        pool = [c for c in report.chunks if not c.is_table and len(c.content) >= 200]
    rng.shuffle(pool)
    return pool[:k]


def make_question(client, chunk) -> str:
    output = client.complete(
        [{"role": "system", "content": QUESTION_PROMPT}, {"role": "user", "content": chunk.content[:1_500]}],
        QUESTION_SCHEMA,
        max_tokens=120,
    )
    return str(output.get("question", "")).strip()


def rank_of(hits, accepted: str | set[str]) -> int | None:
    """정답 문단(여러 개면 그중 아무것)이 처음 나오는 순위."""
    wanted = {accepted} if isinstance(accepted, str) else accepted
    for index, hit in enumerate(hits, start=1):
        if hit.chunk.evidence_id in wanted:
            return index
    return None


def load_gold(path: Path) -> dict[str, list[RetrievalCase]]:
    """골드 JSONL → 기업 코드별 문항. status 가 GOLD 인 줄만 쓴다."""
    by_corp: dict[str, list[RetrievalCase]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if str(row.get("status", "GOLD")).upper() != "GOLD":
            continue
        accepted = [str(i) for i in row.get("accepted_evidence_ids") or []]
        primary = str(row.get("evidence_id") or (accepted[0] if accepted else ""))
        if not primary:
            continue
        case = RetrievalCase(str(row["corp_code"]), primary, str(row.get("section_title", "")), str(row["question"]), accepted_evidence_ids=accepted, source="gold")
        by_corp.setdefault(case.corp_code, []).append(case)
    return by_corp


def recall_table(cases: list[RetrievalCase], methods: list[str], ks=(1, 3, 5, 8)) -> dict[str, dict[str, float]]:
    table: dict[str, dict[str, float]] = {}
    for method in methods:
        ranks = [c.ranks.get(method) for c in cases]
        row = {f"recall@{k}": round(sum(1 for r in ranks if r is not None and r <= k) / max(len(ranks), 1), 3) for k in ks}
        row["mrr"] = round(sum(1.0 / r for r in ranks if r is not None) / max(len(ranks), 1), 3)
        table[method] = row
    return table


# --- 실행 -------------------------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corp-code", action="append", required=True)
    parser.add_argument("--out", default="outputs/company-analysis-eval")
    parser.add_argument("--retrieval-questions", type=int, default=8, help="기업당 검색 질문 수")
    parser.add_argument("--skip-facts", action="store_true")
    parser.add_argument("--skip-retrieval", action="store_true")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--gold", type=Path, help="확정 검색 문항 JSONL. 주면 문항을 새로 만들지 않는다")
    args = parser.parse_args()

    service = get_company_chat_service()
    rng = random.Random(args.seed)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    fact_results: list[FactCase] = []
    retrieval_results: list[RetrievalCase] = []
    gold = load_gold(args.gold) if args.gold else None
    started = time.perf_counter()

    for corp_code in dict.fromkeys(args.corp_code):
        facts = service._analysis._repository.load(corp_code)  # noqa: SLF001 — 평가 스크립트는 내부 구성요소를 직접 쓴다
        if facts is None:
            print(f"[{corp_code}] 기업 없음", file=sys.stderr)
            continue
        print(f"\n===== {facts.profile.corp_name} ({corp_code})")

        if not args.skip_facts:
            for case in fact_cases(facts):
                t = time.perf_counter()
                try:
                    result = service.answer(corp_code=corp_code, message=case.question)
                    case.answer = result["message"]
                    case.citations = len(result["citations"])
                    case.verdict = judge(case.answer, case.kind, case.expected_value, case.expected_tokens)
                except Exception as error:  # noqa: BLE001
                    case.answer, case.verdict = f"{type(error).__name__}: {error}", "error"
                case.latency_s = round(time.perf_counter() - t, 1)
                fact_results.append(case)
                print(f"  [{case.verdict:7s} {case.latency_s:5.1f}s] {case.question} → {case.answer[:70]}")

        if not args.skip_retrieval:
            report = service._reports.latest(corp_code)  # noqa: SLF001
            if report is None:
                print("  사업보고서 청크 없음 — 검색 평가 생략")
                continue
            retriever: CompanyRetriever = service._retriever  # noqa: SLF001
            bm25, vector = retriever._indexes(report)  # noqa: SLF001
            encoder = retriever._encoder  # noqa: SLF001
            if gold is not None:
                cases = gold.get(corp_code, [])
                if not cases:
                    print("  골드 문항 없음 — 검색 평가 생략")
            else:
                cases = []
                for chunk in sample_chunks(report, args.retrieval_questions, rng):
                    try:
                        question = make_question(service._client, chunk)  # noqa: SLF001
                    except Exception as error:  # noqa: BLE001
                        print(f"  질문 생성 실패: {type(error).__name__}", file=sys.stderr)
                        continue
                    if question:
                        cases.append(RetrievalCase(corp_code, chunk.evidence_id, chunk.section_title, question))
            known = report.by_id()
            for case in cases:
                missing = [i for i in case.accepted() if i not in known]
                if missing:
                    print(f"  정답 문단이 현재 청크에 없음({len(missing)}건) — 건너뜀: {case.question}", file=sys.stderr)
                    continue
                question, accepted = case.question, case.accepted()
                case.ranks["bm25"] = rank_of(bm25.search(question, top_k=8), accepted)
                if vector is not None and encoder is not None:
                    try:
                        case.ranks["vector"] = rank_of(vector.search(encoder.encode(question), top_k=8), accepted)
                    except Exception:  # noqa: BLE001
                        case.ranks["vector"] = None
                case.ranks["hybrid"] = rank_of(retriever.search(report, question, top_k=8), accepted)
                retrieval_results.append(case)
                print(f"  [bm25={case.ranks.get('bm25')} vec={case.ranks.get('vector')} hyb={case.ranks.get('hybrid')}] {question}")

    # --- 요약 ---
    summary: dict[str, object] = {"generated_at": stamp, "corp_codes": list(dict.fromkeys(args.corp_code)), "elapsed_s": round(time.perf_counter() - started)}
    lines = [f"# 기업 분석 평가 {stamp}", ""]
    if fact_results:
        counts = {v: sum(1 for c in fact_results if c.verdict == v) for v in ("correct", "abstain", "wrong", "error")}
        total = len(fact_results)
        summary["facts"] = {**counts, "total": total, "accuracy": round(counts["correct"] / total, 3), "wrong_rate": round(counts["wrong"] / total, 3),
                            "avg_latency_s": round(sum(c.latency_s for c in fact_results) / total, 1)}
        lines += ["## 숫자 질문 정확도 (정답 = DB 확정 지표)", "", "| 판정 | 건수 |", "|---|---|"] + [f"| {k} | {v} |" for k, v in counts.items()]
        lines += ["", f"정확도 {summary['facts']['accuracy']:.1%}, 오답률 {summary['facts']['wrong_rate']:.1%}, 평균 {summary['facts']['avg_latency_s']}초 (총 {total}문항)", ""]
        wrong = [c for c in fact_results if c.verdict == "wrong"]
        if wrong:
            lines += ["### 오답", ""] + [f"- **{c.corp_name} · {c.question}** → `{c.answer[:120]}` (기대: {c.expected_tokens[0]})" for c in wrong] + [""]
    if retrieval_results:
        methods = [m for m in ("bm25", "vector", "hybrid") if any(m in c.ranks for c in retrieval_results)]
        table = recall_table(retrieval_results, methods)
        summary["retrieval"] = {"questions": len(retrieval_results), **table}
        lines += ["## 검색 Recall@k (질문 = 문단에서 LLM 생성, 정답 = 그 문단)", "", "| 방식 | R@1 | R@3 | R@5 | R@8 | MRR |", "|---|---|---|---|---|---|"]
        lines += [f"| {m} | {t['recall@1']} | {t['recall@3']} | {t['recall@5']} | {t['recall@8']} | {t['mrr']} |" for m, t in table.items()]
        origin = "사람이 확정한 골드 문항" if gold is not None else "LLM 생성 문항(정제 전)"
        lines += ["", f"질문 {len(retrieval_results)}개({origin}). 정답 문단이 여러 개인 문항은 그중 최상위 순위로 채점. 벡터는 저장된 Qwen3-Embedding 문서 벡터 + 원격 질의 임베딩, 하이브리드는 RRF.", ""]

    (out_dir / f"eval-{stamp}.json").write_text(
        json.dumps({"summary": summary, "facts": [asdict(c) for c in fact_results], "retrieval": [asdict(c) for c in retrieval_results]}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    (out_dir / f"eval-{stamp}.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n" + "\n".join(lines))
    print(f"saved: {out_dir / f'eval-{stamp}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

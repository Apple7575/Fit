# 기업 분석 담당 평가

`python -m ai.scripts.evaluate_company_analysis --corp-code <8자리> ... --out <폴더>` 로 돌린다.
GPU Qwen·서비스 DB·사업보고서 청크 DB가 필요하고, 환경변수는 `ai/company_analysis/api.py` 와 같다.
결과는 `eval-<시각>.json`(원본)과 `eval-<시각>.md`(요약)로 남는다. 기록은 [`results/`](results/) 에 둔다.

## 1. 숫자 질문 정확도

정답을 사람이 만들지 않는다. `company_metric` 의 최신 연도 확정값이 정답이다. 기업마다 6문항을 자동으로 만든다.

| 문항 | 정답 출처 | 채점 |
| --- | --- | --- |
| 매출액·영업이익·당기순이익 | `company_metric` (연결 우선) | 답 속 금액 표기(97.1조원 / 97조 1,468억원 / 97,146,675백만원)를 원으로 환산해 0.5% 이내 |
| 직원 수 | `company_metric.employee_count` | 정수 일치 |
| 영업이익률·부채비율 | 확정값으로 계산 | ±0.15%p |

판정은 넷이다. `correct`(정답) / `abstain`(근거 없다고 답함) / `wrong`(다른 값) / `error`(예외).
**`wrong` 이 안전 지표**다. 틀린 숫자가 사용자에게 나간 비율이므로 0 에 가까워야 한다. `abstain` 은 도움이 안 된 비율이다.

## 2. 검색 Recall@k

사업보고서의 서술 문단(200자 이상, 사업·재무 관련 절)을 기업당 8개 뽑고, Qwen 이 "이 문단만 읽으면 답할 수 있는
취준생 질문"을 만든다. 그 질문으로 기업 안에서 검색해 원래 문단이 상위 k 에 들어오는지 본다.

- `bm25`: 키워드(한글 2·3글자 조각 토큰)
- `vector`: 저장된 Qwen3-Embedding 문서 벡터 + 원격 질의 임베딩, 코사인
- `hybrid`: 둘을 RRF 로 합침 (실제 채팅이 쓰는 방식)

Recall@1/3/5/8 과 MRR 을 낸다. 채팅은 상위 8건을 LLM 에 넣으므로 **Recall@8 이 "답할 근거가 모델에 도달했는가"** 다.
생성된 질문은 JSON 에 남으므로 사람이 검토해 골드 문항으로 승격시킬 수 있다.

## 골드 문항으로 평가하기

LLM 이 만든 검색 문항은 참고치다. 사람이 확정한 문항은 `gold/retrieval.jsonl` 에 두고 `--gold` 로 넘긴다.

```
python -m ai.scripts.build_retrieval_review            # results/*.json 의 문항 + BM25 후보 → gold/retrieval-review-draft.{md,jsonl}
# 사람이 draft.md 를 보고 문항별 유지·수정·삭제와 추가 정답 문단을 정한 뒤 확정 줄만 status=GOLD 로 gold/retrieval.jsonl 에 남긴다
python -m ai.scripts.evaluate_company_analysis --gold ai/evals/company_analysis/gold/retrieval.jsonl --skip-facts --corp-code ...
```

골드 한 줄은 `corp_code`, `question`, `evidence_id`(대표 정답), `accepted_evidence_ids`(정답으로 인정하는 문단 전부), `status` 를 가진다.
"주력 제품이 뭐야" 처럼 여러 문단이 답인 질문은 `accepted_evidence_ids` 에 여러 개를 넣고, 순위는 그중 최상위로 채점한다.

## 한계

- 숫자 문항은 확정 지표가 있는 항목만 다룬다. 사업 설명·경쟁 구도 같은 서술 품질은 측정하지 않는다.
- 검색 문항은 LLM 이 만든 것이라 문단 표현을 그대로 옮긴 쉬운 질문이 섞일 수 있다. 사람 검토 전까지 참고치다.
- 대상 기업은 청크가 있는 100개사 중에서만 고를 수 있다.

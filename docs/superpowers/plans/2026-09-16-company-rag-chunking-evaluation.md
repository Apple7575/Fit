# Company RAG Chunking Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 세 청킹 프로필을 동일한 100개 기업과 동일한 임베딩 모델로 비교해 운영 기본 프로필을 선택한다.

**Architecture:** 프로필별 PostgreSQL 실험 DB는 유지하고, 동일 질의를 각 DB에 실행해 검색 결과를 비교한다. 청킹 비교 단계에서는 벡터 검색 외 변수를 고정하고, 승자를 고른 뒤에만 BM25·하이브리드 검색·리랭커를 추가한다.

**Tech Stack:** Python 3.12, psycopg 3, NumPy, Qwen3-Embedding-0.6B, PostgreSQL

**Spec:** `ai/docs/evaluation-experiment-plan.md`

## Global Constraints

- 대상 기업은 `outputs/company-context-quality/experiment-100-v1.json`의 고정 100개사다.
- 튜닝 80개사와 홀드아웃 20개사를 섞지 않는다.
- 세 프로필 모두 Qwen3-Embedding-0.6B, 1024차원을 사용한다.
- 기업 코드 필터를 검색 전에 적용하며 다른 기업 근거 포함률은 0이어야 한다.
- 청킹 비교 단계에서는 리랭커와 질문 재작성을 사용하지 않는다.
- 별도 커밋·푸시·MR은 평가 완료 전까지 만들지 않는다.

---

### Task 1: 임베딩 완결성 게이트

**Files:**
- Read: `outputs/company-context-quality/experiment-100-v1/embedding-run.stdout.log`
- Read: `outputs/company-context-quality/experiment-100-v1/*.embedding-result.json`
- Read: `outputs/company-context-quality/experiment-100-v1/*-summary.json`

**Interfaces:**
- Consumes: 프로필별 `rag_evidence`, `rag_evidence_embedding`
- Produces: 프로필별 근거 수, 임베딩 수, 차원, 누락 수 검증 결과

- [ ] adaptive-v1 완료 후 `rag_evidence`와 해당 버전 `rag_evidence_embedding` 건수가 같은지 조회한다.
- [ ] 임베딩 차원이 전부 1024인지 확인한다.
- [ ] 동일 `evidence_id` 중복과 `content_hash` 불일치가 0건인지 확인한다.
- [ ] adaptive-v1 완료 뒤 배치 256을 실제 청크 3회로 벤치마크한다.
- [ ] 배치 256이 모두 성공하고 128 대비 처리량이 15퍼센트 이상 증가하면 v2 잔여분에 적용한다.
- [ ] 기준을 통과하지 못하면 배치 128로 v2 잔여분을 재개한다.
- [ ] 세 프로필 임베딩 건수와 오류 수를 JSON 결과로 저장한다.

### Task 2: 검색 평가셋 v1 구축

**Files:**
- Create: `ai/evals/company_context/retrieval-queries-v1.jsonl`
- Create: `ai/evals/company_context/retrieval-rubric-v1.md`
- Modify: `ai/evals/company_context/README.md`

**Interfaces:**
- Consumes: 튜닝 기업 20개사의 사업보고서 청크와 `evidence_id`
- Produces: 질의, 기업 코드, 기준일, 관련 근거 ID, 관련도 등급

- [ ] 튜닝 기업 20개사를 업종과 청크 수 구간이 겹치지 않게 고른다.
- [ ] 기업별로 BUSINESS, PERFORMANCE, TECHNOLOGY_RND, INVESTMENT_STRATEGY, DISCLOSED_RISKS 질의를 한 개씩 작성한다.
- [ ] 질의 100개마다 직접 관련 근거를 2단계 관련도로 표시한다.
- [ ] 숫자 질의에는 연도, 단위, 연결·별도 기준을 정답에 포함한다.
- [ ] 질의 작성에 사용하지 않은 홀드아웃 20개사는 최종 검증용으로 유지한다.
- [ ] 삼성전자 기존 평가 사례와 근거 ID가 현재 코퍼스에 존재하는지 검증한다.

### Task 3: 프로필 독립 벡터 검색기

**Files:**
- Create: `data/pipeline/rag_corpus/vector_search.py`
- Create: `data/tests/rag_corpus/test_vector_search.py`

**Interfaces:**
- Consumes: `search(conn, query_vector, corp_code, embedding_model, embedding_version, top_k)`
- Produces: 점수 순으로 정렬된 `evidence_id`, `content_hash`, `score`, `metadata`

- [ ] 기업 코드 필터가 없는 호출을 거부하는 실패 테스트를 작성한다.
- [ ] 다른 기업 근거가 반환되지 않는 실패 테스트를 작성한다.
- [ ] little-endian float32 벡터 복원과 코사인 점수 정렬 테스트를 작성한다.
- [ ] 테스트 실패를 확인한 뒤 최소 검색 구현을 작성한다.
- [ ] 전체 RAG 코퍼스 테스트를 실행한다.

### Task 4: 청킹 프로필 비교 실행기

**Files:**
- Create: `data/pipeline/rag_corpus/chunking_evaluation.py`
- Create: `data/scripts/run_rag_chunking_evaluation.py`
- Create: `data/tests/rag_corpus/test_chunking_evaluation.py`

**Interfaces:**
- Consumes: 검색 평가셋과 프로필별 DB URL
- Produces: Recall@1, Recall@3, Recall@5, MRR, nDCG@10, 중복률, 검색 지연시간

- [ ] 정답 근거 순위로 Recall과 MRR을 계산하는 실패 테스트를 작성한다.
- [ ] 관련도 등급으로 nDCG@10을 계산하는 실패 테스트를 작성한다.
- [ ] 동일 원문 구간 반복률과 다른 기업 포함률을 계산하는 실패 테스트를 작성한다.
- [ ] 테스트 실패를 확인한 뒤 최소 평가 구현을 작성한다.
- [ ] 세 DB를 같은 질의 순서, 같은 top-k, 같은 쿼리 임베딩으로 실행한다.
- [ ] 원시 결과 JSONL과 집계 CSV를 `outputs/company-context-quality/evaluation-v1`에 저장한다.

### Task 5: 승자 선택과 홀드아웃 검증

**Files:**
- Create: `ai/docs/company-rag-chunking-evaluation-v1.md`

**Interfaces:**
- Consumes: 튜닝 평가 결과와 홀드아웃 평가 결과
- Produces: 운영 기본 청킹 프로필과 재검토 조건

- [ ] 다른 기업 포함률 또는 기준일 이후 자료 포함률이 0이 아닌 프로필을 탈락시킨다.
- [ ] Recall@5, MRR, nDCG@10, 중복률, p50과 p95 검색시간을 비교한다.
- [ ] 주요 검색 지표 차이가 2퍼센트포인트 이하면 청크 수와 저장량이 적은 프로필을 선택한다.
- [ ] 선택한 프로필을 홀드아웃 20개사에 한 번만 실행한다.
- [ ] 튜닝 대비 Recall@5 하락이 5퍼센트포인트를 넘으면 평가셋과 청킹 규칙을 재검토한다.
- [ ] 결과표에 선택 근거, 감수한 비용, 재검토 조건을 기록한다.

### Task 6: 선택 프로필 검색 고도화

**Files:**
- Modify: `data/pipeline/rag_corpus/vector_search.py`
- Create: `data/pipeline/rag_corpus/hybrid_search.py`
- Create: `data/tests/rag_corpus/test_hybrid_search.py`

**Interfaces:**
- Consumes: 선택한 청킹 프로필의 벡터 결과와 BM25 결과
- Produces: RRF 기반 하이브리드 검색 결과

- [ ] 벡터 단독과 BM25 단독 기준값을 고정한다.
- [ ] 기업 필터가 두 검색 경로 모두에 적용되는 실패 테스트를 작성한다.
- [ ] RRF 결합과 동일 원문 구간 중복 억제 테스트를 작성한다.
- [ ] 하이브리드가 Recall@5를 높이는지 동일 평가셋으로 비교한다.
- [ ] Recall@5 개선이 2퍼센트포인트 미만이면 복잡도를 추가하지 않고 벡터 단독을 유지한다.
- [ ] 리랭커는 하이브리드 검색의 오류 사례가 확인된 경우에만 별도 실험한다.

### Task 7: 2,640개사 확장 여부 결정

**Files:**
- Modify: `ai/docs/company-rag-chunking-evaluation-v1.md`

**Interfaces:**
- Consumes: 홀드아웃 통과 결과와 선택 프로필 저장량
- Produces: 전체 코퍼스 재구축 승인 또는 청킹 재실험 결정

- [ ] 홀드아웃 검색 품질과 안전 기준 통과 여부를 확인한다.
- [ ] 선택 프로필의 전체 2,640개사 청크 수, 임베딩 시간, DB 저장량을 추정한다.
- [ ] 통과하면 전체 코퍼스와 임베딩 구축을 시작한다.
- [ ] 실패하면 오류 유형에 대응하는 청킹 프로필 하나만 추가하고 같은 평가셋으로 재검증한다.

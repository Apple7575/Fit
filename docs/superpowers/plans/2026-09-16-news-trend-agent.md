# News and Trend Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a synchronous evidence-grounded `news` agent that reads stored company news first, performs at most one bounded Google News RSS fallback search, relates verified signals to one JD, and runs both directly and through the LangGraph supervisor.

**Architecture:** Add an isolated `ai/news_intelligence/` package with strict Pydantic contracts, a PostgreSQL repository, deterministic coverage/evidence utilities, a bounded search provider, a Qwen boundary, and one orchestration service. Mount it at `/news`, then register a `news` adapter in the existing supervisor without changing JD or position internals.

**Tech Stack:** Python 3, FastAPI, Pydantic v2, psycopg 3, Qwen structured output, Google News RSS parsing utilities, LangGraph, `unittest`

**Spec:** `docs/superpowers/specs/2026-09-16-news-trend-agent-design.md`

## Global Constraints

- Use URL-version-free internal paths; the direct endpoint is `POST /news/internal/analyses`.
- Require both `job_context_id` and `corp_code`; never query `cover_letter` or infer a company code from a name.
- Read stored news from PostgreSQL before considering external search.
- Use a 90-day window, at most 20 stored candidates, and the approved five-candidate/30-day freshness gate.
- Perform at most one external search attempt, one RSS request, 20 returned candidates, and a 30-second provider deadline.
- Never persist external results, crawl article bodies, add embeddings, or change the batch collector.
- Use only article metadata actually observed: title, source/publisher, published time, URL, guid, and stored importance score.
- Calculate evidence levels in deterministic code; the LLM may not raise them.
- Keep the service synchronous and stateless; total supervisor target time remains 120 seconds.
- Final-review budget correction: share one request-local monotonic 90-second news-worker budget across DB, coverage/retries, RSS and extraction/retries. Clamp Qwen/RSS to remaining time; set transaction-local SQL statement_timeout to at most 5 seconds; reject late results and exhausted retries with typed errors. This is best effort, not a hard end-to-end 120-second cancellation guarantee; see spec section 11 and API handoff limitations.
- Spring schema changes, Spring context assembly, and frontend rendering are outside this plan.
- Do not add runtime dependencies unless the standard library and current `ai/requirements.txt` cannot implement the requirement.

---

### Task 1: Define news domain and API contracts

**Files:**
- Create: `ai/news_intelligence/__init__.py`
- Create: `ai/news_intelligence/contracts.py`
- Create: `ai/tests/news_intelligence/__init__.py`
- Create: `ai/tests/news_intelligence/test_contracts.py`

**Interfaces:**
- Consumes: existing supervisor conversation shape (`message_id`, `role`, `content`)
- Produces: `NewsAnalysisRequest`, `NewsCandidate`, `NewsContext`, `CoverageAssessment`, `SignalDraft`, `NewsAnalysis`, `NewsAnalysisResponse`

- [ ] **Step 1: Write failing contract tests**

```python
import unittest
from pydantic import ValidationError

from ai.news_intelligence.contracts import NewsAnalysisRequest, NewsCandidate


class NewsContractsTest(unittest.TestCase):
    def test_requires_both_context_identifiers(self):
        with self.assertRaises(ValidationError):
            NewsAnalysisRequest(instruction="최근 변화", job_context_id="ctx", corp_code="")

    def test_rejects_non_dart_corp_code(self):
        with self.assertRaises(ValidationError):
            NewsAnalysisRequest(instruction="최근 변화", job_context_id="ctx", corp_code="123")

    def test_candidate_keeps_observed_metadata(self):
        candidate = NewsCandidate(
            article_id="stored:1", origin="STORED", title="투자 확대",
            publisher="연합뉴스", published_at="2026-09-10T00:00:00Z",
            url="https://example.com/1", guid="g-1", importance_score=8.0,
        )
        self.assertEqual(candidate.origin, "STORED")
        self.assertEqual(candidate.importance_score, 8.0)
```

- [ ] **Step 2: Run the focused tests and confirm the import failure**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.news_intelligence.test_contracts -v`

Expected: `ModuleNotFoundError: No module named 'ai.news_intelligence'`.

- [ ] **Step 3: Implement strict contracts**

Define exact literals and limits in `contracts.py`:

```python
Scope = Literal["COMPANY", "INDUSTRY", "ROLE"]
CoverageState = Literal["COVERED", "INSUFFICIENT"]
EvidenceLevel = Literal["HIGH", "MEDIUM", "LOW", "INSUFFICIENT"]
Origin = Literal["STORED", "EXTERNAL"]

class NewsAnalysisRequest(StrictModel):
    instruction: str = Field(min_length=1, max_length=10_000)
    job_context_id: str = Field(min_length=1, max_length=80)
    corp_code: str = Field(pattern=r"^[0-9]{8}$")
    conversation: list[ConversationMessage] = Field(default_factory=list, max_length=20)

class NewsCandidate(StrictModel):
    article_id: str
    origin: Origin
    title: str
    publisher: str | None = None
    published_at: datetime
    url: HttpUrl
    guid: str | None = None
    importance_score: float | None = Field(default=None, ge=0, le=10)
```

Add `NewsContext(corp_code, corp_name, industry_name, position_name, jd_text, role_elements)`, coverage/search models, source/signal models, and an overall response whose `analysis_status` is `COMPLETED | INSUFFICIENT_EVIDENCE`. Reject blank trimmed strings with field validators and forbid extra fields everywhere.

- [ ] **Step 4: Run contract tests**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.news_intelligence.test_contracts -v`

Expected: all tests pass.

- [ ] **Step 5: Commit the contracts**

```bash
git add ai/news_intelligence/__init__.py ai/news_intelligence/contracts.py ai/tests/news_intelligence
git commit -m "feat: define news intelligence contracts"
```

### Task 2: Implement deterministic deduplication, coverage gates, and evidence levels

**Files:**
- Create: `ai/news_intelligence/evidence.py`
- Create: `ai/news_intelligence/coverage.py`
- Create: `ai/tests/news_intelligence/test_evidence.py`
- Create: `ai/tests/news_intelligence/test_coverage.py`

**Interfaces:**
- Consumes: `NewsCandidate`, `CoverageAssessment`
- Produces: `deduplicate_candidates(candidates)`, `calculate_evidence_level(candidates, now)`, `decide_external_search(candidates, coverage, now)`

- [ ] **Step 1: Write failing utility tests**

```python
def test_deduplicates_by_url_then_guid_then_normalized_title(self):
    result = deduplicate_candidates([
        candidate("stored:1", url="https://a.test/1", guid="g1", title="AI 투자 확대"),
        candidate("external:1", url="https://a.test/1", guid=None, title="다른 표기"),
        candidate("external:2", url="https://b.test/2", guid="g1", title="재전송"),
        candidate("external:3", url="https://c.test/3", guid=None, title="  AI   투자 확대 "),
    ])
    self.assertEqual([item.article_id for item in result], ["stored:1"])

def test_recent_independent_publishers_are_high_evidence(self):
    sources = [
        candidate("stored:1", publisher="A", days_old=5),
        candidate("stored:2", publisher="B", days_old=12),
    ]
    self.assertEqual(calculate_evidence_level(sources, NOW), "HIGH")

def test_missing_requested_scope_triggers_one_search(self):
    decision = decide_external_search(
        candidates=[candidate(f"stored:{index}", days_old=index) for index in range(5)],
        coverage=CoverageAssessment(company="COVERED", industry="INSUFFICIENT", role="COVERED"),
        requested_scopes={"COMPANY", "INDUSTRY", "ROLE"}, now=NOW,
    )
    self.assertTrue(decision.required)
    self.assertEqual(decision.missing_scopes, ["INDUSTRY"])
```

- [ ] **Step 2: Run focused tests and verify missing functions**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.news_intelligence.test_evidence ai.tests.news_intelligence.test_coverage -v`

Expected: import errors for `evidence` and `coverage`.

- [ ] **Step 3: Implement deterministic rules**

Implement URL canonicalization that removes fragments, normalized guid comparison, and Unicode/whitespace/case title normalization. Preserve the first candidate so stored candidates win when the service concatenates stored before external.

```python
def calculate_evidence_level(sources: Sequence[NewsCandidate], now: datetime) -> EvidenceLevel:
    valid = [item for item in sources if timedelta(0) <= now - item.published_at <= timedelta(days=90)]
    recent = [item for item in valid if now - item.published_at <= timedelta(days=30)]
    recent_publishers = {normalize_publisher(item.publisher) for item in recent if item.publisher}
    all_publishers = {normalize_publisher(item.publisher) for item in valid if item.publisher}
    if len(recent_publishers) >= 2:
        return "HIGH"
    if recent or len(all_publishers) >= 2:
        return "MEDIUM"
    if valid:
        return "LOW"
    return "INSUFFICIENT"
```

`decide_external_search` must return required when there are fewer than five candidates, the newest candidate is older than 30 days, or a requested scope is insufficient. It must return a stable reason and sorted missing scopes.

- [ ] **Step 4: Run utility tests**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.news_intelligence.test_evidence ai.tests.news_intelligence.test_coverage -v`

Expected: all tests pass, including boundary cases at exactly 30 and 90 days.

- [ ] **Step 5: Commit deterministic utilities**

```bash
git add ai/news_intelligence/evidence.py ai/news_intelligence/coverage.py ai/tests/news_intelligence/test_evidence.py ai/tests/news_intelligence/test_coverage.py
git commit -m "feat: add news evidence and coverage rules"
```

### Task 3: Add the PostgreSQL context and stored-news repository

**Files:**
- Create: `ai/news_intelligence/repository.py`
- Create: `ai/tests/news_intelligence/test_repository.py`
- Create: `ai/tests/news_intelligence/test_postgres_repository.py`

**Interfaces:**
- Consumes: `job_context_id: str`, `corp_code: str`, `since: datetime`, `limit: int`
- Produces: `NewsRepository.load_context(job_context_id: str, corp_code: str) -> NewsContext`, `NewsRepository.list_recent(corp_code: str, since: datetime, limit: int) -> list[NewsCandidate]`

- [ ] **Step 1: Write repository contract and SQL-mapping tests**

```python
class FakeNewsRepository:
    def load_context(self, job_context_id, corp_code):
        if job_context_id != "ctx-1":
            raise JobContextNotFound(job_context_id)
        if corp_code != "00126380":
            raise CompanyNotFound(corp_code)
        return NewsContext(
            corp_code=corp_code, corp_name="삼성전자", industry_name="반도체",
            position_name="백엔드 개발자", jd_text="서비스 개발",
            role_elements=[{"name": "API 개발"}],
        )

def test_maps_news_rows_to_stored_candidates(self):
    repository = PostgresNewsRepository("postgresql://unused", connect=fake_connect)
    rows = repository.list_recent("00126380", SINCE, 20)
    self.assertEqual(rows[0].article_id, "stored:17")
    self.assertEqual(rows[0].origin, "STORED")
```

- [ ] **Step 2: Run tests and confirm the repository is absent**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.news_intelligence.test_repository ai.tests.news_intelligence.test_postgres_repository -v`

Expected: import error for `ai.news_intelligence.repository`.

- [ ] **Step 3: Implement repository protocol, errors, and PostgreSQL adapter**

Use injected `connect` for unit tests and default to `psycopg.connect(database_url, connect_timeout=5, row_factory=dict_row)`. `load_context` performs explicit parameterized reads from `ai_job_contexts` and `company LEFT JOIN industry`; it raises `JobContextNotFound` or `CompanyNotFound` rather than returning partial context.

`list_recent` must run this bounded query shape:

```sql
SELECT id, title, source, published_at, original_url, guid, importance_score
FROM news_article
WHERE corp_code = %s
  AND published_at >= %s
  AND title IS NOT NULL
  AND btrim(title) <> ''
  AND original_url IS NOT NULL
ORDER BY published_at DESC, importance_score DESC NULLS LAST, id DESC
LIMIT %s
```

Map `source` to `publisher`, prefix IDs with `stored:`, and wrap psycopg operational errors in `NewsSourceUnavailable` without exposing credentials.

- [ ] **Step 4: Add an opt-in real PostgreSQL integration test**

Use `JD_TEST_DATABASE_URL`; skip when absent. Insert a unique company, context, and news row in a transaction that rolls back, then verify `load_context` and `list_recent`. Do not change production migrations.

```python
@unittest.skipUnless(os.environ.get("JD_TEST_DATABASE_URL"), "JD_TEST_DATABASE_URL is not set")
def test_reads_context_and_recent_news_from_postgres(self):
    repository = PostgresNewsRepository(os.environ["JD_TEST_DATABASE_URL"])
    context = repository.load_context(self.context_id, self.corp_code)
    rows = repository.list_recent(self.corp_code, self.now - timedelta(days=90), 20)
    self.assertEqual(context.position_name, "통합테스트 직무")
    self.assertEqual([row.article_id for row in rows], [f"stored:{self.news_id}"])
```

- [ ] **Step 5: Run repository tests**

Run: `.venv\Scripts\python.exe -m unittest discover -s ai/tests/news_intelligence -p "test_*repository.py" -t . -v`

Expected: unit tests pass; integration test passes when `JD_TEST_DATABASE_URL` exists and otherwise reports one intentional skip.

- [ ] **Step 6: Commit the repository**

```bash
git add ai/news_intelligence/repository.py ai/tests/news_intelligence/test_repository.py ai/tests/news_intelligence/test_postgres_repository.py
git commit -m "feat: query stored news context"
```

### Task 4: Build the bounded Google News RSS search provider

**Files:**
- Create: `ai/news_intelligence/search_provider.py`
- Create: `ai/tests/news_intelligence/test_search_provider.py`
- Modify: `data/news_poc/tests/test_collect.py`

**Interfaces:**
- Consumes: company name, position name, missing scopes, date range, limit
- Produces: `NewsSearchProvider.search(corp_name: str, position_name: str, missing_scopes: Sequence[Scope], from_date: date, to_date: date, limit: int) -> list[NewsCandidate]`

- [ ] **Step 1: Write failing provider tests**

```python
def test_google_provider_makes_one_bounded_request(self):
    fetcher = Mock(return_value=RSS_BYTES)
    provider = GoogleNewsRssProvider(fetcher=fetcher, now=lambda: NOW)
    rows = provider.search(
        corp_name="삼성전자", position_name="백엔드 개발자",
        missing_scopes=["INDUSTRY"], from_date=date(2026, 6, 18),
        to_date=date(2026, 9, 16), limit=20,
    )
    self.assertEqual(fetcher.call_count, 1)
    self.assertLessEqual(len(rows), 20)
    self.assertTrue(all(item.origin == "EXTERNAL" for item in rows))

def test_rate_limit_is_not_retried(self):
    fetcher = Mock(side_effect=HTTPError(URL, 429, "limited", {}, None))
    with self.assertRaises(ExternalSearchUnavailable):
        GoogleNewsRssProvider(fetcher=fetcher).search(**REQUEST)
    self.assertEqual(fetcher.call_count, 1)
```

- [ ] **Step 2: Run tests and verify the provider is missing**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.news_intelligence.test_search_provider -v`

Expected: import error for `search_provider`.

- [ ] **Step 3: Implement one-request provider**

Define a `NewsSearchProvider` protocol and `GoogleNewsRssProvider`. Build exactly one `https://news.google.com/rss/search` URL with `hl=ko`, `gl=KR`, and `ceid=KR:ko`. Quote the canonical company name and add only deterministic terms for missing scopes plus the position name. Add `after:` and `before:` bounds.

Reuse `parse_feed` and `screen_quality` from `data.news_poc`; do not call `build_plan`, `main`, filesystem checkpoint functions, or the CLI. The default fetcher uses `urllib.request.urlopen` with a 25-second timeout and a 10 MB response limit. It does not retry, so the provider stays below the 30-second budget.

Map accepted rows to `external:<article_key>` candidates, discard rows without a parseable timezone-aware date or valid URL, sort newest first, and truncate to the requested limit.

- [ ] **Step 4: Preserve PoC collector regression coverage**

Add a test to `data/news_poc/tests/test_collect.py` proving imports from the AI provider do not invoke `main`, write files, or change `build_plan` behavior.

```python
def test_runtime_provider_import_does_not_run_collector_cli(self):
    with patch("data.news_poc.pipeline.collect.main") as main:
        from ai.news_intelligence.search_provider import GoogleNewsRssProvider
        self.assertIsNotNone(GoogleNewsRssProvider)
    main.assert_not_called()
    self.assertEqual(len(build_plan(date(2026, 9, 1), date(2026, 9, 2))), 2)
```

- [ ] **Step 5: Run provider and PoC tests**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.news_intelligence.test_search_provider -v`

Run: `.venv\Scripts\python.exe -m unittest discover -s data/news_poc/tests -t . -v`

Expected: both suites pass with no network calls.

- [ ] **Step 6: Commit the provider**

```bash
git add ai/news_intelligence/search_provider.py ai/tests/news_intelligence/test_search_provider.py data/news_poc/tests/test_collect.py
git commit -m "feat: add bounded news search provider"
```

### Task 5: Add structured Qwen analysis, validation, and rendering

**Files:**
- Create: `ai/news_intelligence/prompt.py`
- Create: `ai/news_intelligence/model.py`
- Create: `ai/news_intelligence/render.py`
- Create: `ai/tests/news_intelligence/test_model.py`
- Create: `ai/tests/news_intelligence/test_render.py`

**Interfaces:**
- Consumes: `NewsContext`, candidate metadata, instruction, conversation
- Produces: `NewsModel.classify_coverage(context: NewsContext, candidates: Sequence[NewsCandidate], instruction: str) -> CoverageAssessment`, `NewsModel.extract_signals(context: NewsContext, candidates: Sequence[NewsCandidate], instruction: str, conversation: Sequence[ConversationMessage]) -> list[SignalDraft]`, `render_news_message(analysis: NewsAnalysis) -> str`

- [ ] **Step 1: Write failing structured-output tests**

```python
def test_model_sends_metadata_only_and_validates_candidate_ids(self):
    qwen = FakeQwen()
    model = QwenNewsModel(CONFIG, qwen_caller=qwen)
    drafts = model.extract_signals(CONTEXT, CANDIDATES, "영향을 알려줘", [])
    self.assertEqual(drafts[0].source_ids, ["stored:1", "stored:2"])
    payload = json.loads(qwen.calls[-1]["messages"][-1]["content"])
    self.assertNotIn("article_body", json.dumps(payload))

def test_unknown_source_id_is_rejected(self):
    model = QwenNewsModel(CONFIG, qwen_caller=FakeQwen(source_ids=["invented:9"]))
    with self.assertRaises(NewsOutputError):
        model.extract_signals(CONTEXT, CANDIDATES, "분석", [])
```

- [ ] **Step 2: Run tests and confirm missing modules**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.news_intelligence.test_model ai.tests.news_intelligence.test_render -v`

Expected: import errors for model and render.

- [ ] **Step 3: Implement prompts and JSON schemas**

Create separate schemas `news_coverage_v1` and `news_signals_v1`. Coverage returns the three fixed scope states and requested scopes; signal output returns only scope, title, summary, JD relevance, preparation checks, and candidate IDs. The system prompt must state:

```text
Use only supplied article metadata and JD context.
Do not invent article contents, forecasts, resume sentences, or interview answers.
Preparation checks must ask the applicant to verify or organize existing facts.
Return candidate IDs exactly as provided.
```

Use the existing `call_qwen` boundary with a 30-second timeout per call, `max_tokens=700` for coverage and `max_tokens=1800` for signals. Convert malformed JSON/schema output into `NewsOutputError`.

- [ ] **Step 4: Implement server validation and rendering**

Validate every source ID against the candidate map, limit signals to nine (three per scope), limit preparation checks to three per signal, and rebuild source metadata from candidates instead of trusting model copies. `render_news_message` renders only validated fields and explicitly says when evidence is insufficient.

```python
def resolve_sources(source_ids: Sequence[str], candidates: Sequence[NewsCandidate]) -> list[NewsCandidate]:
    by_id = {candidate.article_id: candidate for candidate in candidates}
    unknown = [source_id for source_id in source_ids if source_id not in by_id]
    if unknown:
        raise NewsOutputError(f"unknown source ids: {', '.join(unknown)}")
    return [by_id[source_id] for source_id in source_ids]

def render_news_message(analysis: NewsAnalysis) -> str:
    if analysis.analysis_status == "INSUFFICIENT_EVIDENCE":
        return "확인 가능한 최신 기사 근거가 부족해 기업·산업·직무 변화를 판단하지 않았습니다."
    return "\n\n".join(f"[{signal.scope}] {signal.title}\n{signal.jd_relevance}" for signal in analysis.signals)
```

- [ ] **Step 5: Run model/render tests**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.news_intelligence.test_model ai.tests.news_intelligence.test_render -v`

Expected: all tests pass; fake Qwen records exactly the two documented schema names.

- [ ] **Step 6: Commit model boundary**

```bash
git add ai/news_intelligence/prompt.py ai/news_intelligence/model.py ai/news_intelligence/render.py ai/tests/news_intelligence/test_model.py ai/tests/news_intelligence/test_render.py
git commit -m "feat: analyze grounded news signals"
```

### Task 6: Orchestrate stored-first analysis in the service

**Files:**
- Create: `ai/news_intelligence/service.py`
- Create: `ai/tests/news_intelligence/test_service.py`

**Interfaces:**
- Consumes: repository, search provider, model, clock, `NewsAnalysisRequest`
- Produces: `NewsIntelligenceService.analyze(request) -> NewsAnalysisResponse`

- [ ] **Step 1: Write failing orchestration tests**

```python
def test_sufficient_stored_news_skips_external_search(self):
    service, provider = build_service(stored=RECENT_STORED, coverage=COVERED)
    response = service.analyze(REQUEST)
    self.assertEqual(provider.calls, [])
    self.assertFalse(response.analysis.external_search.used)

def test_gap_uses_external_search_once_without_saving(self):
    service, provider, repository = build_service(
        stored=RECENT_STORED, coverage=MISSING_INDUSTRY, external=EXTERNAL_ROWS,
    )
    response = service.analyze(REQUEST)
    self.assertEqual(len(provider.calls), 1)
    self.assertFalse(hasattr(repository, "save"))
    self.assertTrue(response.analysis.external_search.used)

def test_no_evidence_returns_insufficient_instead_of_hallucinating(self):
    service = build_service(stored=[], external=[], coverage=ALL_MISSING)[0]
    response = service.analyze(REQUEST)
    self.assertEqual(response.analysis.analysis_status, "INSUFFICIENT_EVIDENCE")
    self.assertEqual(response.analysis.signals, [])
```

- [ ] **Step 2: Run tests and confirm service is absent**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.news_intelligence.test_service -v`

Expected: import error for `service`.

- [ ] **Step 3: Implement the approved pipeline**

Implement this exact order: load context, query 90-day stored candidates with limit 20, deduplicate, classify coverage when deterministic gates do not already require search, decide search, call provider at most once, merge/deduplicate, extract drafts, rebuild verified sources, calculate evidence, create response, render message.

If external search raises `ExternalSearchUnavailable`, continue with stored candidates. If no candidates remain, return `INSUFFICIENT_EVIDENCE` without calling signal extraction. Retry coverage or signal extraction once only when `NewsOutputError` is raised; do not retry repository or provider calls.

- [ ] **Step 4: Add failure and boundary tests**

Cover repository errors, one model retry then failure, external search failure with stored fallback, exact 5-candidate threshold, exactly 30-day freshness, maximum 20 candidates, and source ordering with stored before external.

```python
def test_model_contract_error_retries_once_then_fails(self):
    model = FakeModel(errors=[NewsOutputError("bad-1"), NewsOutputError("bad-2")])
    service = build_service(model=model)[0]
    with self.assertRaises(NewsOutputError):
        service.analyze(REQUEST)
    self.assertEqual(model.extract_calls, 2)

def test_exact_threshold_does_not_search_when_coverage_is_complete(self):
    service, provider = build_service(stored=five_candidates(days_old=30), coverage=COVERED)
    service.analyze(REQUEST)
    self.assertEqual(provider.calls, [])
```

- [ ] **Step 5: Run service tests**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.news_intelligence.test_service -v`

Expected: all tests pass and each fake dependency records the approved call count.

- [ ] **Step 6: Commit service orchestration**

```bash
git add ai/news_intelligence/service.py ai/tests/news_intelligence/test_service.py
git commit -m "feat: orchestrate news intelligence analysis"
```

### Task 7: Expose and mount the direct news API

**Files:**
- Create: `ai/news_intelligence/api.py`
- Create: `ai/tests/news_intelligence/test_api.py`
- Modify: `ai/serve.py`
- Modify: `ai/tests/test_serve.py`

**Interfaces:**
- Consumes: `JD_DATABASE_URL`, `NEWS_QWEN_ENV_FILE` falling back to `ai/.env`
- Produces: `/news/health`, `/news/ready`, `POST /news/internal/analyses`

- [ ] **Step 1: Write failing API and mount tests**

```python
def test_returns_structured_analysis(self):
    fake = FakeNewsService(RESPONSE)
    app.dependency_overrides[get_news_service] = lambda: fake
    response = TestClient(app).post("/internal/analyses", json=VALID_REQUEST)
    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.json(), RESPONSE.model_dump(mode="json"))

def test_mounts_news_service(self):
    client = TestClient(build_app())
    self.assertEqual(client.get("/news/health").status_code, 200)
    self.assertEqual(client.get("/health").json()["services"]["news"], "/news")
```

- [ ] **Step 2: Run tests and verify route failures**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.news_intelligence.test_api ai.tests.test_serve -v`

Expected: news API import or `/news` mount assertions fail.

- [ ] **Step 3: Assemble dependencies and map errors**

Use `@lru_cache(maxsize=1)` for `get_news_service`. Build `PostgresNewsRepository`, `GoogleNewsRssProvider`, and `QwenNewsModel`. Missing DB or Qwen configuration maps to `503`; domain not-found errors map to the spec's `404` codes; malformed requests remain FastAPI `422`; model exhaustion maps to `502`; repository unavailability maps to `503 NEWS_SOURCE_UNAVAILABLE`.

Mount the app in `ai/serve.py`, add it to root health, and include its lifespan only if the implementation owns a resource that needs closing.

- [ ] **Step 4: Run API and root tests**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.news_intelligence.test_api ai.tests.test_serve -v`

Expected: all tests pass without network or PostgreSQL.

- [ ] **Step 5: Commit the direct API**

```bash
git add ai/news_intelligence/api.py ai/tests/news_intelligence/test_api.py ai/serve.py ai/tests/test_serve.py
git commit -m "feat: expose news intelligence api"
```

### Task 8: Register the news worker in the LangGraph supervisor

**Files:**
- Modify: `ai/supervisor/contracts.py`
- Modify: `ai/supervisor/adapters.py`
- Modify: `ai/supervisor/model.py`
- Modify: `ai/supervisor/api.py`
- Modify: `ai/tests/supervisor/test_contracts.py`
- Modify: `ai/tests/supervisor/test_adapters.py`
- Modify: `ai/tests/supervisor/test_model.py`
- Modify: `ai/tests/supervisor/test_graph.py`
- Modify: `ai/tests/supervisor/test_api.py`

**Interfaces:**
- Consumes: `agent_contexts.news = {job_context_id, corp_code}` and `NewsIntelligenceService`
- Produces: supervisor plans/results that allow agent literal `news`

- [ ] **Step 1: Write failing supervisor contract and adapter tests**

```python
def test_news_context_requires_job_and_company_ids(self):
    request = SupervisorRunRequest.model_validate({
        **BASE_REQUEST,
        "agent_contexts": {"news": {"job_context_id": "ctx-1", "corp_code": "00126380"}},
    })
    self.assertEqual(request.agent_contexts.news.corp_code, "00126380")

def test_news_adapter_ignores_applicant_documents(self):
    service = FakeNewsService()
    adapter = NewsAgentAdapter(service)
    result = adapter.execute("최근 변화", DOCUMENTS, CONVERSATION, NEWS_CONTEXT)
    self.assertFalse(hasattr(service.calls[0], "documents"))
    self.assertEqual(result["analysis"]["company"]["corp_code"], "00126380")
```

- [ ] **Step 2: Run supervisor tests and verify `news` is rejected**

Run: `.venv\Scripts\python.exe -m unittest discover -s ai/tests/supervisor -t . -v`

Expected: Pydantic and plan schema failures for unknown `news`.

- [ ] **Step 3: Extend contracts, plan prompt, and adapter registry**

Add `NewsAgentContext(job_context_id, corp_code)`, optional `AgentContexts.news`, and `news` to both agent literals and Qwen plan schema. Describe the capability as “기업·산업·직무 변화의 기사 근거와 JD 관련성 분석”.

`NewsAgentAdapter.execute` constructs a `NewsAnalysisRequest` from instruction, its own two identifiers, and conversation; it does not pass documents. Register it with the cached `get_news_service()` in `get_supervisor_service`, and update the no-context guard to include news.

- [ ] **Step 4: Add graph and mounted-API concurrency coverage**

Add a three-worker test whose fake adapters block on a shared barrier so the test proves JD, position, and news branches are dispatched in parallel. Add mounted API assertions for news-only success, JD+news success, news-only failure producing `ALL_AGENTS_FAILED`, and news failure beside JD success producing `PARTIAL`.

```python
def test_dispatches_three_selected_workers_in_parallel(self):
    barrier = threading.Barrier(3, timeout=1)
    adapters = [BarrierAdapter(name, barrier) for name in ("jd", "position", "news")]
    graph = build_supervisor_graph(
        FakeModel([SupervisorPlan(selected_agents=["jd", "position", "news"], reason="모두 필요")]),
        AgentRegistry(adapters),
    )
    output = graph.invoke(three_agent_state())
    self.assertEqual({item.agent for item in output["agent_results"]}, {"jd", "position", "news"})
    self.assertTrue(all(adapter.passed_barrier for adapter in adapters))
```

- [ ] **Step 5: Run supervisor tests**

Run: `.venv\Scripts\python.exe -m unittest discover -s ai/tests/supervisor -t . -v`

Expected: all supervisor tests pass and plan schemas accept only `jd`, `position`, `news`.

- [ ] **Step 6: Commit supervisor integration**

```bash
git add ai/supervisor ai/tests/supervisor
git commit -m "feat: connect news worker to supervisor"
```

### Task 9: Add evaluation fixtures, API documentation, and full regression verification

**Files:**
- Create: `ai/evals/news_intelligence/schema.json`
- Create: `ai/evals/news_intelligence/cases/company-change-001.json`
- Create: `ai/evals/news_intelligence/cases/industry-gap-001.json`
- Create: `ai/evals/news_intelligence/cases/role-change-001.json`
- Create: `ai/evals/news_intelligence/cases/insufficient-001.json`
- Create: `ai/evals/news_intelligence/cases/conflicting-sources-001.json`
- Create: `ai/tests/news_intelligence/test_evaluation_cases.py`
- Create: `ai/docs/news-trend-agent-api.md`

**Interfaces:**
- Consumes: final request/response contracts and public internal routes
- Produces: validated offline cases and backend-facing API handoff documentation

- [ ] **Step 1: Write a failing fixture validation test**

```python
def test_all_evaluation_cases_match_contracts(self):
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    self.assertEqual(schema["$id"], "news-intelligence-evaluation-v1")
    self.assertEqual(schema["required"], ["status", "request", "stored_candidates", "external_candidates", "expected_response"])
    for path in sorted(CASES.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(set(schema["required"]) - payload.keys(), set(), path.name)
        self.assertEqual(payload["status"], "DRAFT", path.name)
        NewsAnalysisRequest.model_validate(payload["request"])
        NewsAnalysisResponse.model_validate(payload["expected_response"])
```

- [ ] **Step 2: Run the fixture test and confirm files are absent**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.news_intelligence.test_evaluation_cases -v`

Expected: missing schema/case failure.

- [ ] **Step 3: Add five reviewed-shape fixtures**

Each fixture contains the request, stored candidates, optional external candidates, expected scopes/evidence levels, and a contract-valid expected response. Mark cases `DRAFT` and state that they are regression fixtures, not published quality scores. Include one case for each filename listed above.

Use this exact top-level shape for every case:

```json
{
  "status": "DRAFT",
  "request": {
    "instruction": "최근 기업 변화가 직무에 미치는 영향을 알려줘",
    "job_context_id": "fixture-context-1",
    "corp_code": "00126380",
    "conversation": []
  },
  "stored_candidates": [],
  "external_candidates": [],
  "expected_response": {
    "message": "확인 가능한 최신 기사 근거가 부족해 기업·산업·직무 변화를 판단하지 않았습니다.",
    "analysis": {
      "analysis_status": "INSUFFICIENT_EVIDENCE",
      "company": {"corp_code": "00126380", "corp_name": "삼성전자"},
      "window": {"from": "2026-06-18", "to": "2026-09-16"},
      "signals": [],
      "coverage": {"company": "INSUFFICIENT", "industry": "INSUFFICIENT", "role": "INSUFFICIENT"},
      "external_search": {"used": true, "reason": "유효 기사 5건 미만"}
    }
  }
}
```

- [ ] **Step 4: Document the backend handoff**

`ai/docs/news-trend-agent-api.md` must include:

- direct endpoint and supervisor endpoint
- required `job_context_id` and eight-digit `corp_code`
- complete request/response examples
- Spring responsibility for reading `cover_letter` and validating ownership
- `SUCCESS`, `PARTIAL`, `INSUFFICIENT_EVIDENCE`, and HTTP error behavior
- 120-second total timeout expectation and no automatic worker retry
- explicit statement that external results are response-only

- [ ] **Step 5: Run fixture, news, supervisor, PoC, and complete AI suites**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.news_intelligence.test_evaluation_cases -v`

Run: `.venv\Scripts\python.exe -m unittest discover -s ai/tests/news_intelligence -t . -v`

Run: `.venv\Scripts\python.exe -m unittest discover -s ai/tests/supervisor -t . -v`

Run: `.venv\Scripts\python.exe -m unittest discover -s data/news_poc/tests -t . -v`

Run: `.venv\Scripts\python.exe -m unittest discover -s ai/tests -p "test_*.py" -t . -v`

Expected: all non-database tests pass; PostgreSQL integration tests are the only allowed skips when `JD_TEST_DATABASE_URL` is absent. Record the exact run/pass/skip counts in the merge request description.

- [ ] **Step 6: Confirm no external-result persistence path exists**

Run: `rg -n "INSERT INTO news_article|UPDATE news_article|save.*NewsCandidate" ai/news_intelligence`

Expected: no matches.

- [ ] **Step 7: Commit evaluation and documentation**

```bash
git add ai/evals/news_intelligence ai/tests/news_intelligence/test_evaluation_cases.py ai/docs/news-trend-agent-api.md
git commit -m "test: add news agent evaluation fixtures"
```

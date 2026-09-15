# JD Internal API Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 미연동 JD FastAPI 경로를 `/jd/internal` 아래의 리소스형 규칙으로 통일한다.

**Architecture:** `/jd` 앱 마운트와 기존 리소스형 `/internal` 라우트는 유지한다. 동사형·도메인 중복 경로 `/internal/jd/analyze`만 `/internal/analyses`로 교체하며 호환 라우트는 남기지 않는다.

**Tech Stack:** Python 3, FastAPI, Pydantic, unittest, FastAPI TestClient

**Spec:** `docs/superpowers/specs/2026-09-15-position-prompt-agent-design.md`

## Global Constraints

- 공개 Spring API는 변경하지 않는다.
- URL에 API 버전을 넣지 않는다.
- `/health`와 `/docs`는 각 앱 루트에 유지한다.
- `/internal/jd/analyze` 호환 경로는 남기지 않는다.
- API 요청 및 응답 본문 계약은 변경하지 않는다.

---

### Task 1: JD 경로 계약 변경

**Files:**
- Modify: `ai/tests/jd_coaching/test_api.py`
- Modify: `ai/tests/jd_coaching/test_chat_api.py`
- Modify: `ai/jd_coaching/api.py`

**Interfaces:**
- Consumes: 기존 FastAPI request/response 모델과 서비스 메서드
- Produces: 기존 `/internal/job-contexts`, `/internal/analysis-jobs`, `/internal/conversations`와 새 `/internal/analyses`

- [ ] **Step 1: 테스트의 모든 내부 경로를 새 규칙으로 변경하고 레거시 거부 테스트를 추가한다**

```python
def test_legacy_sync_analysis_path_is_not_exposed(self):
    response = self.client.post("/internal/jd/analyze", json=self.valid_request)
    self.assertEqual(response.status_code, 404)
```

- [ ] **Step 2: 변경한 경로 테스트가 실패하는지 확인한다**

Run: `.\.venv\Scripts\python.exe -m unittest ai.tests.jd_coaching.test_api ai.tests.jd_coaching.test_chat_api`

Expected: 새 `/internal/analyses` 요청이 `404`이거나 레거시 경로 거부 테스트가 실패한다.

- [ ] **Step 3: `ai/jd_coaching/api.py`의 라우트 문자열을 일괄 정규화한다**

```python
@app.post("/internal/job-contexts", status_code=201, tags=["internal"])
@app.get("/internal/job-contexts/{context_id}", tags=["internal"])
@app.post("/internal/job-contexts/{context_id}/analyses", tags=["internal"])
@app.post("/internal/job-contexts/{context_id}/analysis-jobs", status_code=202, tags=["internal"])
@app.get("/internal/analysis-jobs/{analysis_id}", tags=["internal"])
@app.post("/internal/conversations", status_code=201, tags=["internal"])
@app.get("/internal/conversations/{conversation_id}", tags=["internal"])
@app.delete("/internal/conversations/{conversation_id}", status_code=204, tags=["internal"])
@app.post("/internal/conversations/{conversation_id}/messages", tags=["internal"])
@app.post("/internal/analyses", response_model=AnalyzeResponse, tags=["internal"])
```

`from-url`과 `from-file`을 포함한 기존 job-context 경로는 변경하지 않는다.

- [ ] **Step 4: JD API 테스트를 실행한다**

Run: `.\.venv\Scripts\python.exe -m unittest ai.tests.jd_coaching.test_api ai.tests.jd_coaching.test_chat_api`

Expected: 모든 테스트가 `OK`다.

- [ ] **Step 5: 변경을 커밋한다**

```bash
git add ai/jd_coaching/api.py ai/tests/jd_coaching/test_api.py ai/tests/jd_coaching/test_chat_api.py
git commit -m "refactor: normalize JD internal API paths"
```

### Task 2: 진입점 문서와 전체 회귀 검증

**Files:**
- Modify: `ai/serve.py`
- Test: `ai/tests`

**Interfaces:**
- Consumes: Task 1의 JD 경로
- Produces: 실제 마운트 경로를 설명하는 최신 진입점 문서

- [ ] **Step 1: `ai/serve.py`의 경로 설명을 `/jd/internal/...`로 유지하고 리소스 규칙을 명시한다**

```python
"""컨테이너 진입점.

    /health                 전체 상태
    /jd/internal/...        JD 기반 자소서 코칭 내부 API
"""
```

- [ ] **Step 2: 전체 AI 테스트를 실행한다**

Run: `.\.venv\Scripts\python.exe -m unittest discover -s ai/tests -p "test_*.py"`

Expected: 전체 테스트가 `OK`이며 JD 경로 관련 `404` 실패가 없다.

- [ ] **Step 3: 공백 오류를 검사한다**

Run: `git diff --check`

Expected: 출력이 없다.

- [ ] **Step 4: 변경을 커밋한다**

```bash
git add ai/serve.py
git commit -m "docs: describe versioned JD API mount"
```

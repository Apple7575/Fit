# Position Agent Generalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the backend-only position profile with one universal experience-depth rubric that validates missing links in user-authored experience claims across job families.

**Architecture:** Keep `POST /position/internal/analyses`, but replace `position_profile_id` with `rubric_id` and structured `position_context`. Qwen extracts a universal `claim_type` and evidence quotes; deterministic Python validation derives the required element set from the rubric and rejects unsupported coverage, verdicts, or source evidence.

**Tech Stack:** Python 3, FastAPI, Pydantic, JSON Schema, `unittest`, Qwen OpenAI-compatible API

**Spec:** `docs/superpowers/specs/2026-09-15-position-agent-generalization-design.md`

## Global Constraints

- Do not modify Spring or frontend code.
- Keep the HTTP path `POST /position/internal/analyses` unchanged.
- Support only `experience-depth-v1`; reject `backend-v1` and `position_profile_id`.
- Treat only `documents` as factual evidence. Position name, JD priorities, assistant messages, and model knowledge are context only.
- Use exact contiguous document quotes and Python string offsets.
- Retry one invalid Qwen output once, then return the existing validation failure path.
- Keep all new evaluation fixtures `DRAFT`; do not publish them as performance metrics.

---

### Task 1: Universal rubric and v2 output contract

**Files:**
- Create: `ai/position_coaching/resources/rubrics/experience-depth-v1.json`
- Create: `ai/position_coaching/resources/schemas/position-analysis-v2.json`
- Modify: `ai/position_coaching/contracts.py`
- Modify: `ai/tests/position_coaching/test_contracts.py`

**Interfaces:**
- Produces: `load_experience_rubric(source) -> dict[str, Any]`
- Produces: `validate_experience_analysis_output(output, documents, rubric) -> dict[str, Any]`
- Produces constants `CLAIM_TYPES`, `ELEMENT_CODES`, `VERDICTS`

- [ ] **Step 1: Write failing rubric-loader tests**

Add tests proving that `experience-depth-v1` loads, every claim type has its canonical required elements, and `backend-v1` is rejected. The core expected mapping must be a hand-written literal:

```python
EXPECTED_CLAIM_TYPES = {
    "PROBLEM_SOLVING": ("PROBLEM", "ROLE", "ACTION", "REASONING", "VERIFICATION", "RESULT"),
    "ACHIEVEMENT": ("SITUATION", "ROLE", "ACTION", "VERIFICATION", "RESULT"),
    "DECISION": ("SITUATION", "ROLE", "ACTION", "REASONING", "RESULT"),
    "EXECUTION": ("SITUATION", "ROLE", "ACTION", "PROCESS", "RESULT"),
    "COLLABORATION": ("SITUATION", "ROLE", "ACTION", "PROCESS", "RESULT"),
    "GROWTH": ("SITUATION", "ACTION", "VERIFICATION", "LEARNING"),
    "OTHER": ("SITUATION", "ROLE", "ACTION", "RESULT"),
}

def test_loads_only_canonical_experience_depth_rubric(self):
    rubric = load_experience_rubric(RUBRIC_PATH)
    actual = {
        item["code"]: tuple(item["required_elements"])
        for item in rubric["claim_types"]
    }
    self.assertEqual(actual, EXPECTED_CLAIM_TYPES)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m unittest ai.tests.position_coaching.test_contracts
```

Expected: import or assertion failure because `load_experience_rubric` and the v2 policy do not exist.

- [ ] **Step 3: Add the rubric and minimal loader**

Create a JSON resource with `schema_version`, `rubric_id`, `version`, `elements`, and the seven exact `claim_types` from the spec. Add `load_experience_rubric` and the canonical claim mapping alongside the v1 loader so modules not yet migrated remain testable. Reject duplicate, unknown, missing, or reordered required elements.

```python
UNIVERSAL_CLAIM_TYPES = {
    "PROBLEM_SOLVING": ("PROBLEM", "ROLE", "ACTION", "REASONING", "VERIFICATION", "RESULT"),
    "ACHIEVEMENT": ("SITUATION", "ROLE", "ACTION", "VERIFICATION", "RESULT"),
    "DECISION": ("SITUATION", "ROLE", "ACTION", "REASONING", "RESULT"),
    "EXECUTION": ("SITUATION", "ROLE", "ACTION", "PROCESS", "RESULT"),
    "COLLABORATION": ("SITUATION", "ROLE", "ACTION", "PROCESS", "RESULT"),
    "GROWTH": ("SITUATION", "ACTION", "VERIFICATION", "LEARNING"),
    "OTHER": ("SITUATION", "ROLE", "ACTION", "RESULT"),
}
```

- [ ] **Step 4: Write failing v2 output-validation tests**

Cover these observable breaks separately:

- output uses `rubric`, `claim_type`, and `NO_EXPERIENCE_CLAIM`;
- model cannot add or omit elements outside the selected claim type partition;
- verdict is derived from coverage (`SUFFICIENT`, `PARTIAL`, `CLAIM_ONLY`);
- exact quote and offset checks still reject fabricated evidence;
- vague claim text can exist while `present_elements` remains empty;
- `NO_EXPERIENCE_CLAIM` requires empty findings.

```python
def test_rejects_element_not_required_by_claim_type(self):
    output = valid_v2_output(claim_type="ACHIEVEMENT")
    output["findings"][0]["present_elements"].append(
        {"element": "LEARNING", "quote": "배웠습니다"}
    )
    with self.assertRaisesRegex(ValueError, "element coverage"):
        validate_experience_analysis_output(output, DOCUMENTS, self.rubric)
```

- [ ] **Step 5: Run the validation tests and verify RED**

Run the same focused command. Expected: failures on v2 field names and universal element codes.

- [ ] **Step 6: Implement the v2 validator and schema**

Make `validate_experience_analysis_output` require exactly:

```python
{"analysis_status", "rubric", "findings", "model_metadata"}
```

Each finding must require exactly:

```python
{
    "finding_id", "claim_type", "claim", "present_elements",
    "missing_elements", "verdict", "reason", "follow_up_questions",
}
```

Use the selected `claim_type` to obtain the server-owned required set. Preserve the current deterministic verdict rule: all required present is `SUFFICIENT`; otherwise presence of `ACTION` is `PARTIAL`; otherwise `CLAIM_ONLY`. Preserve the explicit `NOT_ASSESSABLE` full-missing rule.

- [ ] **Step 7: Run contract tests and verify GREEN**

Run the focused contract suite and confirm all cases pass.

- [ ] **Step 8: Commit the contract change**

```powershell
git add ai/position_coaching/contracts.py ai/position_coaching/resources/rubrics/experience-depth-v1.json ai/position_coaching/resources/schemas/position-analysis-v2.json ai/tests/position_coaching/test_contracts.py
git commit -m "feat: 포지션 범용 분석 계약 추가"
```

---

### Task 2: Generalized prompt and analysis service

**Files:**
- Modify: `ai/position_coaching/prompt.py`
- Modify: `ai/position_coaching/service.py`
- Modify: `ai/tests/position_coaching/test_prompt.py`
- Modify: `ai/tests/position_coaching/test_service.py`

**Interfaces:**
- Consumes: `load_experience_rubric`, `validate_experience_analysis_output`
- Produces: `build_position_messages(rubric, position_context, documents, conversation)`
- Produces: `PositionAnalysisService.analyze(rubric_id, position_context, documents, conversation)`

- [ ] **Step 1: Write failing prompt tests**

Assert that the serialized payload contains `experience_rubric`, `position_context`, documents, and conversation, and contains no `position_profile`. Assert that the system instruction says nontechnical experience is valid, JD priorities are context only, vague verbs are not evidence, and only documents are factual evidence.

```python
payload = json.loads(messages[1]["content"])
self.assertEqual(payload["experience_rubric"]["rubric_id"], "experience-depth-v1")
self.assertEqual(payload["position_context"]["position_name"], "마케팅 매니저")
self.assertNotIn("position_profile", payload)
```

- [ ] **Step 2: Run prompt tests and verify RED**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m unittest ai.tests.position_coaching.test_prompt
```

Expected: signature and payload assertion failures.

- [ ] **Step 3: Implement the generalized prompt**

Replace technical-claim wording with experience-claim wording. Tell Qwen to select one canonical `claim_type`, return exact source evidence, never use `priority_requirements` as evidence, and not invent job-fit feedback. Include the rubric and structured position context in the user payload.

- [ ] **Step 4: Write failing service tests**

Test the new four-argument service call and exact model boundary:

```python
result = service.analyze(
    "experience-depth-v1",
    {"position_name": "마케팅 매니저", "priority_requirements": ["성과 지표 분석"]},
    DOCUMENTS,
    [],
)
self.assertEqual(qwen.calls[0]["schema_name"], "position_analysis_v2")
self.assertEqual(result["rubric"], {"id": "experience-depth-v1", "version": 1})
```

Also assert that `backend-v1` is rejected before Qwen is called and invalid output is retried exactly once.

- [ ] **Step 5: Run service tests and verify RED**

Run the focused service suite. Expected: old three-argument signature and v1 schema assertions fail.

- [ ] **Step 6: Implement service v2**

Load `resources/rubrics/experience-depth-v1.json`, load `position-analysis-v2.json`, set `PROMPT_VERSION = "experience-depth-v1"`, and call the generalized prompt builder. Validate through `validate_experience_analysis_output`. Continue replacing all model-supplied metadata with server-controlled values.

- [ ] **Step 7: Run prompt and service tests and verify GREEN**

Run both focused suites and confirm all tests pass.

- [ ] **Step 8: Commit prompt and service changes**

```powershell
git add ai/position_coaching/prompt.py ai/position_coaching/service.py ai/tests/position_coaching/test_prompt.py ai/tests/position_coaching/test_service.py
git commit -m "feat: 포지션 경험 분석을 직무 독립형으로 변경"
```

---

### Task 3: FastAPI request and deterministic user message

**Files:**
- Modify: `ai/position_coaching/api.py`
- Modify: `ai/position_coaching/render.py`
- Modify: `ai/tests/position_coaching/test_api.py`
- Modify: `ai/tests/position_coaching/test_render.py`

**Interfaces:**
- Consumes: generalized `PositionAnalysisService.analyze`
- Produces request fields `rubric_id`, `position_context`, `documents`, `conversation`
- Produces user-facing messages for all nine universal elements

- [ ] **Step 1: Write failing API contract tests**

Use this minimal valid request:

```python
VALID_REQUEST = {
    "rubric_id": "experience-depth-v1",
    "position_context": {
        "position_name": "마케팅 매니저",
        "priority_requirements": ["성과 지표 분석"],
    },
    "documents": [{
        "document_id": "cover-letter",
        "document_type": "SELF_INTRO",
        "text": "SNS 캠페인을 개선해 전환율을 높였습니다.",
    }],
    "conversation": [],
}
```

Assert a 200 response and exact arguments passed to the fake service. Add separate 422 tests for legacy `position_profile_id`, blank position name, more than 20 priorities, a priority longer than 500 characters, unsupported rubric, invalid document, and invalid conversation role.

- [ ] **Step 2: Run API tests and verify RED**

Run the API test module. Expected: the new fields are rejected by the old Pydantic model.

- [ ] **Step 3: Implement request models and service call**

Add `PositionContextRequest` with `extra="forbid"`, a required stripped `position_name`, and at most 20 stripped priority strings of 1–500 characters. Replace `position_profile_id` with `rubric_id` and forward all four service arguments.

- [ ] **Step 4: Write failing renderer tests**

Cover `SITUATION`, `PROCESS`, and `LEARNING` labels and the new no-claim message:

```python
message = render_position_message({
    "analysis_status": "NO_EXPERIENCE_CLAIM",
    "findings": [],
})
self.assertIn("구체화할 경험", message)
self.assertNotIn("기술 경험", message)
```

- [ ] **Step 5: Run renderer tests and verify RED**

Run the renderer test module. Expected: missing label lookup or old technical-claim copy.

- [ ] **Step 6: Implement universal renderer copy**

Use the stable element order from the spec. Keep ignoring model-authored `reason` and `follow_up_questions`; render only validated claim quotes and missing element templates so unsupported claims cannot reach the user message.

- [ ] **Step 7: Run API and renderer tests and verify GREEN**

Run both focused modules and confirm all tests pass.

- [ ] **Step 8: Commit API and renderer changes**

```powershell
git add ai/position_coaching/api.py ai/position_coaching/render.py ai/tests/position_coaching/test_api.py ai/tests/position_coaching/test_render.py
git commit -m "refactor: 포지션 분석 API를 범용 루브릭 계약으로 전환"
```

---

### Task 4: Cross-role evaluation contract and draft fixtures

**Files:**
- Modify: `ai/position_coaching/evaluation.py`
- Modify: `ai/scripts/validate_position_eval_set.py`
- Modify: `ai/tests/position_coaching/test_evaluation.py`
- Create: `ai/evals/position_coaching/evaluation-policy-v2.json`
- Create: `ai/evals/position_coaching/cases-v2/schema.json`
- Create: `ai/evals/position_coaching/cases-v2/draft/*.json` (12 cases)
- Modify: `ai/evals/position_coaching/canonical-v1-review-guide.md`

**Interfaces:**
- Consumes: v2 analysis contract and universal rubric
- Produces: v2 case fields `rubric_id`, `position_context`, and expected `claim_type`
- Preserves: canonical-v1 files as explicitly historical, non-runnable fixtures

- [ ] **Step 1: Write failing v2 evaluation tests**

Replace v1 case helpers with v2 literals. Assert that cases require `experience-depth-v1`, position context, universal claim types, exact required-element partitions, and `DRAFT` cases cannot be scored as official metrics. Rename metric dimensions from experience type to claim type.

- [ ] **Step 2: Run evaluation tests and verify RED**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m unittest ai.tests.position_coaching.test_evaluation
```

Expected: failures because evaluation code still requires `backend-v1` and `experience_type`.

- [ ] **Step 3: Implement the v2 evaluation contract**

Validate `rubric_id`, `position_context`, `claim_type`, exact quote, verdict, and element partition using the same rubric loader as production. Update the candidate-set validator to require 12 cases, at least six position names, at least six claim types, and three examples for each verdict. Keep `required_label_status` equal to `DRAFT` for this regression-only seed set and make the scoring function continue requiring `HUMAN_APPROVED`.

- [ ] **Step 4: Add 12 independently readable draft cases**

Add two cases each for backend, frontend, data, marketing, sales, and HR. Across the complete set include all seven claim types and exactly three cases per verdict. Every expected quote must occur literally in its document, and every present/missing list must partition the rubric-owned required set. Do not copy backend technology nouns into nontechnical cases.

- [ ] **Step 5: Run the fixture validator and verify GREEN**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' ai/scripts/validate_position_eval_set.py --policy ai/evals/position_coaching/evaluation-policy-v2.json --case ai/evals/position_coaching/cases-v2/draft/backend-001.json --case ai/evals/position_coaching/cases-v2/draft/backend-002.json --case ai/evals/position_coaching/cases-v2/draft/frontend-001.json --case ai/evals/position_coaching/cases-v2/draft/frontend-002.json --case ai/evals/position_coaching/cases-v2/draft/data-001.json --case ai/evals/position_coaching/cases-v2/draft/data-002.json --case ai/evals/position_coaching/cases-v2/draft/marketing-001.json --case ai/evals/position_coaching/cases-v2/draft/marketing-002.json --case ai/evals/position_coaching/cases-v2/draft/sales-001.json --case ai/evals/position_coaching/cases-v2/draft/sales-002.json --case ai/evals/position_coaching/cases-v2/draft/hr-001.json --case ai/evals/position_coaching/cases-v2/draft/hr-002.json --report outputs/position-lora/generalization-v2-validation.json
```

Expected: exit code 0, `valid: true`, `case_count: 12`, and no issues. The generated report remains ignored under `outputs/`.

- [ ] **Step 6: Mark canonical v1 artifacts as historical**

Update the review guide to state that canonical-v1 and `evaluation-policy-v1.json` belong to the merged backend-only contract and are not inputs to the v2 evaluator. Do not mechanically relabel the 60 existing cases.

- [ ] **Step 7: Run evaluation tests and verify GREEN**

Run both evaluation test modules and confirm all tests pass.

- [ ] **Step 8: Commit evaluation changes**

```powershell
git add ai/position_coaching/evaluation.py ai/scripts/validate_position_eval_set.py ai/tests/position_coaching/test_evaluation.py ai/evals/position_coaching/evaluation-policy-v2.json ai/evals/position_coaching/cases-v2 ai/evals/position_coaching/canonical-v1-review-guide.md
git commit -m "test: 포지션 범용 분석 다직무 평가 기반 추가"
```

---

### Task 5: API documentation, dead resources, and full verification

**Files:**
- Modify: `docs/api/position-analysis-api.md`
- Delete: `ai/position_coaching/resources/profiles/backend-v1.json`
- Delete: `ai/position_coaching/resources/schemas/position-analysis-v1.json`

**Interfaces:**
- Documents the exact Spring-to-FastAPI request and response contract.
- Leaves no production import or API example referencing `backend-v1`.

- [ ] **Step 1: Update the API document**

Document `rubric_id`, `position_context`, v2 output fields, the evidence boundary, 422/502 behavior, and the absence of Spring integration. Clearly distinguish JD fit analysis from position experience-depth analysis.

- [ ] **Step 2: Remove dead v1 production resources**

Delete the backend-only profile, v1 output schema, and temporary v1-only loader and validator after all production and evaluation imports use the new resources. Keep historical evaluation fixtures and design history, which must remain explicitly labeled as v1.

- [ ] **Step 3: Check active-code references**

Run:

```powershell
rg -n "backend-v1|position_profile_id|position_profile|NO_TECHNICAL_CLAIM|experience_type" ai/position_coaching ai/tests/position_coaching docs/api/position-analysis-api.md
```

Expected: no matches except assertions that verify legacy input rejection.

- [ ] **Step 4: Run the full AI test suite**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m unittest discover -s ai/tests -p 'test_*.py'
```

Expected: all tests pass, with only the pre-existing optional PostgreSQL integration skip.

- [ ] **Step 5: Verify repository scope and whitespace**

Run:

```powershell
git diff --check
git diff --name-only origin/develop
git status --short
```

Expected: only `.gitignore`, `Decisions/`, `docs/`, and `ai/` position-analysis files; no `backend/`, `frontend/`, or `infra/` changes; clean working tree after the final commit.

- [ ] **Step 6: Commit documentation and cleanup**

```powershell
git add docs/api/position-analysis-api.md ai/position_coaching/resources/profiles/backend-v1.json ai/position_coaching/resources/schemas/position-analysis-v1.json
git commit -m "docs: 포지션 범용 분석 API 명세 갱신"
```

- [ ] **Step 7: Run final verification after commit**

Repeat the full AI suite, fixture validator, `git diff --check`, and scope check. Record the exact command outputs in the handoff; do not claim success from earlier runs.

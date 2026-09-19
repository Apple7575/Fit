# Company Evaluation Table Context Implementation Plan

> **For agentic workers:** Use inline execution in the current worktree. No commit or MR, per user request.

**Goal:** Re-audit the 100-company silver evaluation set and prevent unsupported table numbers from passing future automatic validation.

**Architecture:** Keep the generated silver JSONL immutable. A deterministic audit writes a separate review-status file. New generation carries table header and detectable unit alongside each row and fails closed when numeric table context is absent.

**Tech Stack:** Python, unittest, DART XML Document parser

**Spec:** Approved conversation on 2026-09-16: audit existing cases first, then repair evaluation question/evidence generation. This does not alter RAG chunking or embeddings.

## Global Constraints

- Preserve the existing 500-case JSONL and its manifest.
- Preserve human decisions for cases 1–5 in the separate review file.
- Do not commit or create an MR.

---

### Task 1: Conservative audit of existing cases

**Files:**
- Create: `data/pipeline/rag_corpus/evaluation_audit.py`
- Create: `data/scripts/audit_company_retrieval_eval.py`
- Create: `data/tests/rag_corpus/test_evaluation_audit.py`

**Interfaces:**
- Consumes existing JSONL case fields.
- Produces one audit result per case with `case_id`, `audit_status`, and `reasons`, plus a summary. `audit_status` is `REVIEWABLE` or `NEEDS_CONTEXT`, never a gold approval.

- [ ] Write tests showing a numeric table row without header/unit, an unsupported year/percentage claim, and a direct paragraph answer.
- [ ] Run the new tests and confirm the expected failures.
- [ ] Implement pure `audit_case(case)` and a CLI that reads but never mutates the silver JSONL.
- [ ] Run tests and audit all 500 cases; verify case count, source preservation, and known false positives.

### Task 2: Preserve table context in future generated candidates

**Files:**
- Modify: `data/pipeline/rag_corpus/evaluation_dataset.py`
- Modify: `data/pipeline/rag_corpus/evaluation_generation.py`
- Modify: `data/tests/rag_corpus/test_evaluation_dataset.py`
- Modify: `data/tests/rag_corpus/test_evaluation_generation.py`

**Interfaces:**
- Consumes `Document` table matrices and `Document.unit(table)`.
- Produces table source units with header rows and source unit, and validation rejects numeric table cases when the quote omits this context.

- [ ] Write tests using multi-row headers and a numeric table without a verifiable unit.
- [ ] Run targeted tests and confirm they fail for the observed reason.
- [ ] Include table headers and detected unit in source-unit text; force numeric table quotes to include the complete context or reject them.
- [ ] Run targeted and full `data/tests/rag_corpus` suites.
- [ ] Audit a small new-generation pilot without overwriting the existing silver output.

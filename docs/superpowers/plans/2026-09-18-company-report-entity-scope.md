# Company Report Entity Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 사업보고서 자회사 표의 수치를 대상 기업 전체 실적으로 쓰지 못하게 한다.

**Architecture:** XML 파서가 명시적 `【 법인명 】` 제목을 표에 연결하고, 근거 ID별 보조 테이블에 소속을 적재한다. 기존 근거 해시와 벡터는 유지한다. API는 보조 테이블을 조회해 생성 모델과 결정적 범위 검사에 전달한다.

**Tech Stack:** Python 3.11, unittest, lxml, PostgreSQL/Flyway, FastAPI.

**Spec:** `docs/superpowers/specs/2026-09-18-company-report-entity-scope-design.md`

## Global Constraints

- `rag_evidence.content_hash`와 `rag_evidence_embedding.content_hash`를 변경하지 않는다.
- 대상 기업명으로 자회사 소속을 추정하지 않는다. XML의 명시적 제목만 인정한다.
- 뉴스 관련 코드는 변경하지 않는다.
- 기존 `.runtime/` 및 API 작업트리의 삭제된 사용자 파일은 보존한다.

---

### Task 1: XML 표의 명시적 소속 추출

**Files:** `data/pipeline/business_report/doc.py`, `data/tests/raw_sources/test_business_report.py`

**Interfaces:** `Table.entity_scope: str | None`을 제공한다.

- [ ] 테스트: `<TITLE>실적</TITLE><P>【 우리자산운용 】</P><TABLE>...22,133...</TABLE><P>【 우리은행 】</P><TABLE>...</TABLE><TITLE>다음 장</TITLE><TABLE>...</TABLE>`에서 표별 소속이 `우리자산운용`, `우리은행`, `None`인지 확인한다.
- [ ] `python -m unittest data.tests.raw_sources.test_business_report`로 테스트가 예상대로 실패하는지 확인한다.
- [ ] `Table`에 선택적 `entity_scope`를 추가하고, `_walk`의 문단에서 `^【\s*([^】]+?)\s*】$` 전체 일치일 때만 값을 바꾸며 `TITLE`에서 초기화한다.
- [ ] 같은 테스트와 `data/tests/raw_sources` 전체를 실행한다.

### Task 2: 범위 보조 테이블과 멱등 백필

**Files:** `backend/src/main/resources/db/migration/V27__rag_evidence_entity_scope.sql`, `data/pipeline/raw_sources/entity_scope.py`, `data/scripts/backfill_rag_entity_scope.py`, `data/tests/raw_sources/test_entity_scope.py`

**Interfaces:** `scope_rows(archive: DartArchive, corp_code: str, profile: ChunkingProfile) -> list[tuple[str, str, str, int]]`는 `(evidence_id, scope_name, rcept_no, table_index)`를 반환한다.

- [ ] 테스트: 작은 ZIP에서 한 표가 여러 청크로 분할돼도 해당 청크의 안정적 `evidence_id`마다 같은 소속이 연결되고, 명시적 소속이 없는 표는 제외되는지 확인한다.
- [ ] 테스트가 실패하는지 확인한다.
- [ ] `Document.from_bytes`와 기존 `_document_records`의 `source_identity`를 재사용해 테이블 인덱스와 근거 ID를 연결한다. 원본 근거 행은 수정하지 않는다.
- [ ] 마이그레이션에 `evidence_id` 기본키/FK, `scope_name`, `rcept_no`, `table_index`, `rule_version`, `updated_at`을 추가한다. 백필은 입력 100개사 목록만 순회하고 `INSERT ... ON CONFLICT DO UPDATE`로 같은 값을 재실행 가능하게 한다. 존재하지 않는 근거 ID는 건수로 보고한다.
- [ ] 테스트와 SQL 문법 검증을 실행한다. 로컬 DB가 준비되면 백필 전후 기존 해시·임베딩 일치 건수를 비교한다.

### Task 3: API 생성 입력과 결정적 범위 검증

**Files:** `ai/company_context/models.py`, `ai/company_context/postgres_corpus.py`, `ai/company_context/llm/section_writer.py`, `ai/company_context/claim_check.py`, `ai/company_context/service.py`, 관련 `ai/tests/company_context/` 테스트.

**Interfaces:** `EvidenceDocument.entity_scope: str | None = None`; `entity_scope_violations(text: str, cited: Iterable[EvidenceDocument], company: Company) -> list[tuple[str, str]]`.

- [ ] 테스트: `우리금융지주 전체 영업이익 22,133백만원`을 소속 `우리자산운용`인 표만으로 인용하면 탈락하고, `우리자산운용 영업이익 22,133백만원`은 유지한다. 독립적인 전체 실적 근거를 인용한 문장은 소속 표 때문에 불필요하게 탈락시키지 않는다.
- [ ] 테스트가 실패하는지 확인한다.
- [ ] PostgreSQL `LEFT JOIN rag_evidence_entity_scope` 결과를 별도 필드에 넣고, 모델 입력에 `소속 법인`을 추가한다. 생성 후 검사에 법인 범위 검사를 연결한다. 근거·임베딩 해시는 건드리지 않는다.
- [ ] `python -m unittest discover -s ai/tests/company_context -p 'test_*.py'`를 실행한다.

### Task 4: 실제 DB·보고서 검증 및 디에이피 진단

**Files:** `docs/experiments/company-retrieval-eval-2026-09-16.md`, `docs/handoff/company-rag-home-2026-09-17.md`, 필요한 경우 진단 테스트.

- [ ] Docker Desktop 백엔드가 정상화됐는지 확인한다. 오류가 유지되면 DB 초기화 없이 중단하고 로컬 통합 검증을 미완료로 보고한다.
- [ ] 마이그레이션·100개사 백필 후 미연결 근거 0건, 해시·벡터 일치 건수 유지 여부를 SQL로 확인한다.
- [ ] 우리금융지주 보고서를 재생성해 `22,133백만원`이 지주사 전체 실적으로 남지 않는지 확인한다.
- [ ] 디에이피 보고서는 필터 적용 전 상세 6건의 텍스트·인용 ID·위반 코드를 로컬 진단 출력으로 확인하고, 별도 원인과 후속 수정 여부를 기록한다.
- [ ] 기존 5개 보고서와 전체 단위 테스트를 재실행하고 결과를 실험 로그에 기록한다.

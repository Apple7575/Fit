# 기업 분석 RAG 다른 로컬 환경 인수인계 (2026-09-17)

> 2026-09-17 범위 변경: 뉴스 수집·본문 구축·최근 이슈 분석은 별도 뉴스 에이전트의 책임이다. 아래의 기업 분석 후속 작업에는 포함하지 않는다. 기존 실험 결과의 뉴스 섹션 언급은 당시 출력 계약을 설명하는 기록이다.

## 결론과 브랜치

100개 기업의 사업보고서 코퍼스와 1024차원 임베딩으로 FastAPI 보고서 생성까지 실행했다. 다만 보고서 의미 정확도는 아직 통과 판정 전이다. 작업은 두 브랜치에 나뉘어 있으므로 둘 다 받아야 한다.

| 브랜치 | 담당 | 주요 위치 |
| --- | --- | --- |
| `feature/report-chunking` | DART XML 파싱, `adaptive-v1` 청킹, 스테이징·DB 적재, GPU 임베딩, 검색 평가 | `data/pipeline/`, `data/scripts/`, `data/config/company_rag_experiment_100.json`, `docs/experiments/` |
| `feature/company-context-rag-api-baseline` | `POST /company/internal/analyses`, BM25·벡터 검색, 근거 선택, Qwen 보고서 생성·검증 | `ai/company_context/`, `ai/scripts/export_company_report_review.py`, `docs/api/company-report-rag-api.md` |

두 브랜치는 서로 다른 Git 이력을 갖는다. API 코드가 `feature/report-chunking` 안에 들어 있는 것이 아니므로 한 브랜치만 체크아웃해 전체를 실행할 수 없다. 합치거나 MR을 만들기 전에는 두 작업 디렉터리를 별도로 사용한다.

## 지금까지 한 일

- `dart_local.zip`의 사업보고서를 100개사로 선택했다. 선정 목록은 `data/config/company_rag_experiment_100.json`에 보존한다(튜닝 80, 홀드아웃 20).
- `ROWSPAN=n`의 마지막 행이 빠지는 표 파서 버그를 수정했다. `table-rowspan-v2` 파서로 다시 청킹한 실험 DB `ca_rag_adaptive_rowspan_v2`에는 DART 근거 631,068건과 같은 원문 해시의 `Qwen/Qwen3-Embedding-0.6B` / `adaptive-v1` 벡터 631,068건이 있다. 이 DB는 **현재 PC의 로컬 PostgreSQL**에만 있으며 Git에는 없다.
- FastAPI가 이 DB를 조회하고 GPU 서버의 임베딩 API와 Qwen 생성 API를 호출해 7개 섹션 보고서를 반환한다. 실제 삼성전자 요청 `POST /company/internal/analyses`는 HTTP 200이었다.
- 5개사(나노솔루션 `01924673`, 덕산테코피아 `01021666`, 디에이피 `00303192`, 삼성전자 `00126380`, 우리금융지주 `01350869`) 보고서를 새 코퍼스로 재생성했다. 최신 5건에서 뉴스 제외 30개 섹션 중 25개가 `AVAILABLE`, 상세 134건의 인용 ID 누락·타기업 근거·기준일 이후 근거는 각각 0건이었다. 이는 형식 검사이며 의미 정확도 점수가 아니다.
- 예비 검색 질문 4건의 BM25 Top-10 적중은 3건이다. 확정 골드 정답은 0건이다.

## 알려진 문제와 다음 작업

1. 우리금융지주 보고서의 `2025년 전체 영업이익 22,133백만원`은 **우리자산운용** 항목 아래의 표에서 나온 값이다. 원본 `document_20260313001235.xml`에서 표 앞의 `【 우리자산운용 】` 제목을 확인했다. 인용 청크에는 상위 법인명이 빠져 있어 지주사 전체 실적으로 오인했다. 숫자 일치만으로 법인 범위를 검증할 수 없으므로 청킹 단계에서 표의 소속 법인을 보존해야 한다.
2. 디에이피 실적 섹션은 숫자 검증 뒤 상세 0건으로 `INSUFFICIENT_EVIDENCE`다. 이전 v1 출력에서는 원문 `543,196,074천원`을 `543,196천원`으로 잘라 쓴 생성 오류가 확인된다. 최신 실행에서 제외된 6개 문장의 원문은 저장되지 않아 동일 원인인지 아직 확인하지 못했다. 2026-09-18 재현 시 로컬 PostgreSQL `localhost:55432` 연결이 타임아웃됐다. Docker Desktop 실행 파일을 찾아 시작했으나 백엔드가 `dockerInference` 소켓 오류로 종료됐다(`AppData/Local/Docker/log/host/com.docker.backend.exe.log`). 해당 0바이트 잔여 소켓을 보존하며 이름 변경을 시도했지만 Windows가 접근을 거부했다. 데이터 초기화는 하지 않았다. DB를 다시 연결한 뒤 원문·검색 후보·생성 문장·검사 사유를 함께 기록해 원인을 확인한다.
3. 현재 기술 섹션 장 제목 필터와 영업부문 표 검사는 좁은 안전장치다. 기업별 예외를 더 쌓지 말고 법인·부문·기간·연결/별도·단위 범위를 공통 구조로 다루는 방향으로 재평가한다.
4. 대표 기업의 검색 질문과 정답 근거를 사람이 확정한 평가셋이 아직 필요하다. 평가는 기업 분석 범위인 사업보고서·공시 근거에 집중한다.

## 2026-09-18 로컬 진행 상태

- `feature/report-chunking`에서 XML의 `【 법인명 】` 제목을 뒤따르는 표와 연결하는 파서, 근거 ID별 소속 보조 테이블 마이그레이션 `V27__rag_evidence_entity_scope.sql`, 백필 도구 `python -m data.scripts.backfill_rag_entity_scope`를 추가했다. 기존 근거 본문·메타데이터·해시는 수정하지 않는다.
- `feature/company-context-rag-api-baseline`에서 보조 테이블의 `entity_scope`를 조회·생성 입력·최종 근거 응답에 전달하고, 자회사 표만 인용한 기업 전체 실적 문장을 제외하도록 했다. **두 브랜치를 합치고 DB 마이그레이션·백필을 실행하기 전에는 실제 API 조회가 새 테이블을 찾지 못한다.**
- 원본 ZIP에서 우리금융지주 `22,133백만원` 근거 ID `dart-business-report-0c304f6cd4c5f9f9ae40952762f821ae`가 `우리자산운용`으로 연결됨을 확인했다. 같은 기업의 기존 스테이징 13,375건과 재생성 근거를 비교해 ID 추가·누락 0건, `content_hash` 변경 0건이었다. 따라서 이 기업의 기존 임베딩 재계산은 필요하지 않다.
- 단위 테스트는 코퍼스 `data/tests/raw_sources` 54건, `data/tests/rag_corpus` 153건, API `ai/tests/company_context` 157건이 통과했다. 100개사 XML dry run 결과(`outputs/company-context-quality/entity-scope-100-dry-run.json`)는 `company_count=100`, 소속 법인 후보가 있는 기업 8개, 후보 표 2,206건이다. 이 수치는 추출 후보이지 DB 근거 ID와 일치하거나 보고서에 반영된 건수가 아니다. 우리금융지주 `01350869`의 후보가 2,011건으로 집중되어 표본 정확도 검토가 필요하다. 2026-09-18에 중지된 실험 DB 컨테이너 `dart-data-pg-local`을 재기동하고 `ca_rag_adaptive_rowspan_v2`에서 근거·임베딩 각 631,068건을 확인한 뒤 V27을 적용했다. 100개사 실제 백필은 진행 중이며, 완료 전에는 일치·누락 건수나 보고서 재생성 성공을 주장하지 않는다.
- 백필 시 `DATABASE_URL`은 실행 프로세스 환경이나 해당 작업트리 `data/.env`에서 제공해야 한다. 원본 ZIP·선정 목록을 지정하고 먼저 `--dry-run`을 실행한 뒤, Flyway V27 적용 후 같은 명령에서 `--dry-run`만 빼서 적재한다. `missing_count`는 0이어야 한다.

## 집 PC 준비

Git에서 두 브랜치를 받고, `feature/report-chunking` 디렉터리에서 코퍼스를 준비한 뒤 `feature/company-context-rag-api-baseline` 디렉터리에서 FastAPI를 실행한다. Python·PostgreSQL·Docker와 의존성 설치 방법은 각 브랜치의 `data/README.md`, `ai/README.md`를 따른다. 실행 전 최신 코드의 CLI `--help`로 인자를 확인한다.

```powershell
git fetch origin feature/report-chunking feature/company-context-rag-api-baseline
git switch --track origin/feature/report-chunking
git worktree add --track -b feature/company-context-rag-api-baseline ..\company-context-rag-api origin/feature/company-context-rag-api-baseline
```

`feature/report-chunking`의 `.env.example`을 참고해 로컬 `data/.env`에 PostgreSQL URL과 임베딩 서버 설정을 넣는다. `feature/company-context-rag-api-baseline`의 `ai/.env.example`을 참고해 로컬 `ai/.env`에 Qwen 설정을 넣는다. 실제 비밀번호와 API 키는 Git에 넣지 않았다. 현재 원격 임베딩 서버는 OpenAI 호환 `POST /v1/embeddings`를 제공하며, `GET /v1/models`에서 확인한 served model ID는 `main`이었다. 서버를 다시 띄우거나 주소가 바뀌면 ID를 재확인한다.

```powershell
# API 작업 디렉터리에서 사용할 환경 변수의 핵심 값(비밀값은 로컬 .env에서 읽을 것)
$env:RAG_CORPUS_BACKEND = 'postgres'
$env:RAG_COMPANY_PATH = 'data/config/company_universe.csv'
$env:RAG_EMBEDDING_MODEL = 'Qwen/Qwen3-Embedding-0.6B'
$env:RAG_EMBEDDING_VERSION = 'adaptive-v1'
$env:RAG_EMBEDDING_SERVED_MODEL = 'main'
$env:RAG_MODEL_TIMEOUT_SECONDS = '180'
# DATABASE_URL: ca_rag_adaptive_rowspan_v2를 가리켜야 함
# RAG_EMBEDDING_BASE_URL, RAG_EMBEDDING_API_KEY, QWEN_BASE_URL,
# QWEN_MODEL, QWEN_API_KEY도 해당 서버 설정에 맞게 주입
python -m ai.scripts.export_company_report_review --corp-code 00126380 --as-of 2026-09-16 --output outputs/samsung-review.json
```

## Git에 없는 자료와 이동 방법

- `C:\Users\SSAFY\Downloads\dart_local.zip`: 사업보고서 XML 원본, 약 2.66GB. 다른 PC로 안전하게 복사하거나 DART에서 다시 수집해야 한다. 원본이 없으면 같은 100개사 코퍼스를 재구축할 수 없다.
- `outputs/company-context-quality/experiment-100-rowspan-v2/staging/adaptive-v1/`: 100개사 압축 청크 약 193MB. 원본 ZIP과 청킹 스크립트로 재생성 가능하다. 복사할 경우 요약 JSON 안의 `records_path`가 이전 PC 절대경로인지 확인하고 다시 생성하거나 경로를 갱신한다.
- PostgreSQL DB `ca_rag_adaptive_rowspan_v2`: 631,068개 근거와 벡터. Git에 없다. 다른 PC에서 그대로 조회하려면 PostgreSQL 백업을 별도로 옮기고 복원해야 한다. 백업이 없다면 원본 ZIP → `adaptive-v1` 청킹 → DB 적재 → GPU 임베딩을 다시 실행한다. 마이그레이션에는 `V26__rag_evidence_embedding.sql`이 필요하다.
- 로컬 `ai/.env`, `data/.env`: 키·비밀번호를 담고 있어 Git에 없다. 집 PC에서 각각 새로 설정한다.
- `outputs/company-context-quality/rowspan-v2-reports-scope-gate-v3/`: 5개 보고서의 상세 원문이 들어 있는 로컬 검토 산출물. Git에는 실험 요약만 남긴다.

원본 ZIP·DB·스테이징을 Git에 넣지 않았다는 뜻은 **브랜치 푸시만으로 집 PC에서 즉시 같은 보고서를 재생성할 수는 없다**는 뜻이다. 데이터 파일을 별도 이동하거나 위 파이프라인으로 다시 구축해야 한다.

## 검증 기준

API 브랜치에서는 `python -m unittest discover -s ai/tests/company_context -p 'test_*.py'`를 실행한다. 코퍼스 브랜치에서는 먼저 `PYTHONPATH=data`를 설정하고 `python -m unittest discover -s data/tests/rag_corpus -p 'test_*.py'`, `python -m unittest discover -s data/tests/raw_sources -p 'test_*.py'`를 실행한다. 2026-09-17 확인 결과 각각 153개, 48개와 API 148개가 통과했다. 전체 `data/tests` 285개 중 1개는 뉴스 종단 테스트가 `data_fields.csv`에 아직 반영되지 않은 다른 도메인의 Flyway 필드 108개 때문에 실패했다. 나머지 7개는 스킵됐다. 선정 파일은 `company_count=100`, `groups.tuning=80`, `groups.holdout=20`, 고유 법인코드 100개로 확인했다. 테스트 통과는 보고서 의미 정확도를 보증하지 않는다.

상세 시도·실패·수정 기록은 `docs/experiments/company-retrieval-eval-2026-09-16.md`에 있다.

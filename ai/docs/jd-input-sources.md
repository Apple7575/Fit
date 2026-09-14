# JD 입력 경로

이 문서의 엔드포인트는 Spring 메인 백엔드가 내부 네트워크에서 호출하는 AI 서비스 API다. 브라우저와 프론트엔드가 직접 호출하지 않는다.

Spring은 사용자 인증, 지원 세션 연결, 사용자에게 허용할 파일 형식과 크기 검증, 원본 파일 저장·삭제를 담당한다. FastAPI는 전달받은 파일이나 URL을 JD 텍스트로 정규화하고 요구사항을 구조화한다. FastAPI는 업로드 원본을 영구 저장하지 않는다.

FastAPI의 실행 저장소는 프로젝트 PostgreSQL을 사용한다. `JD_DATABASE_URL`이 없거나 PostgreSQL URL이 아니면 저장소를 생성하지 않는다. SQLite 저장소는 단위 테스트와 로컬 저장소 계약 검증에만 사용한다.

## 지원 입력

| 입력 | 엔드포인트 | 필수 메타데이터 | 처리 방식 |
|---|---|---|---|
| 직접 입력 | `POST /internal/job-contexts` | 기업명, 직무명, JD 텍스트 | 입력 텍스트를 그대로 사용 |
| URL | `POST /internal/job-contexts/from-url` | URL | HTML 본문과 Schema.org `JobPosting` 메타데이터 추출 |
| 파일 | `POST /internal/job-contexts/from-file` | 기업명, 직무명, 파일 | TXT·MD·HTML·PDF·DOCX에서 텍스트 추출 |

URL에 `JobPosting` 구조화 데이터가 있으면 기업명, 직무명, 공고 ID, 게시일과 마감일을 가져온다. 요청에 기업명이나 직무명을 함께 보내면 사용자가 입력한 값을 우선한다. 구조화 데이터가 없고 두 값을 요청에서도 제공하지 않으면 `422`를 반환한다.

프론트엔드에서는 PDF·DOCX·TXT만 사용자 선택 형식으로 제공한다. MD·HTML은 외부 사용자 계약이 아니라 내부 변환기의 호환 형식이다.

파일 입력은 원본 파일을 저장하지 않는다. 추출한 JD 텍스트와 원본 파일명, 원본 바이트의 SHA-256만 지원 컨텍스트에 저장한다. Spring은 반환된 `context_id`를 자신의 지원 세션 및 사용자와 연결한다.

## URL 입력 예시

```http
POST /internal/job-contexts/from-url
Content-Type: application/json

{
  "url": "https://careers.example.com/jobs/123",
  "company_name": "예시기업",
  "position_name": "백엔드 엔지니어",
  "source_type": "OFFICIAL_CAREERS_SITE"
}
```

## 파일 입력 예시

```powershell
curl.exe -X POST http://localhost:8000/internal/job-contexts/from-file `
  -F "company_name=예시기업" `
  -F "position_name=백엔드 엔지니어" `
  -F "file=@posting.pdf"
```

## 제한과 오류

- 입력 원본은 최대 10 MiB, 추출된 텍스트는 최대 50,000자다.
- URL 입력은 HTTP와 HTTPS만 허용하며 로컬·사설 네트워크 주소와 해당 주소로의 리다이렉트를 거절한다.
- 브라우저에서 JavaScript를 실행해야 본문이 나타나는 채용 사이트는 추출에 실패할 수 있다. 이 경우 파일 또는 직접 입력을 사용한다.
- 이미지와 텍스트 레이어가 없는 스캔 PDF에는 OCR이 필요하다. 현재 API는 이를 `422`로 반환한다.
- 지원하지 않는 파일과 URL 응답 형식은 `415`, 외부 URL 호출 실패는 `502`로 반환한다.

## 서비스 호출 흐름

```text
프론트엔드
  → Spring: 사용자 인증, 지원 세션, 파일 수명 관리
    → FastAPI 내부 API: JD 텍스트 추출과 구조화
      → Qwen: 요구사항 추출과 사용자 경험 연결 판정
    ← context_id와 분석 결과
  ← 사용자 화면에 표시할 응답
```

## 데이터베이스 설정

```env
JD_DATABASE_URL=postgresql://ssafy:${POSTGRES_PASSWORD}@postgres:5432/company_analysis
```

Flyway의 `V20__jd_ai_analysis.sql`이 `ai_job_contexts`와 `ai_analysis_jobs`를 생성한다. 완료 또는 실패한 분석 작업은 결과를 저장한 뒤 AI 테이블에 임시 보관한 사용자 문서 내용을 제거한다.

PostgreSQL이 실행되고 Flyway가 적용된 환경에서는 다음 명령으로 실제 저장·조회·입력 문서 제거까지 검증한다.

```powershell
$env:JD_TEST_DATABASE_URL = "postgresql://..."
python -m unittest ai.tests.jd_coaching.test_postgres_store.PostgresStoreIntegrationTest
```

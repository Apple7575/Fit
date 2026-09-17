---
type: decision
status: active
date: 2026-09-13
project: JD 기반 자소서 코칭
supersedes: []
superseded_by: []
---

## 문제

사용자가 업로드하는 JD 파일과 URL을 Spring 메인 백엔드와 AI FastAPI 중 어느 서비스가 받아야 하는가.

## 결정

브라우저의 외부 요청은 Spring이 받는다. Spring은 인증, 지원 세션, 허용 파일 정책과 원본 파일의 저장·삭제를 책임진다.

FastAPI의 JD 입력 엔드포인트는 `/internal` 아래에 두고 Spring이 호출한다. FastAPI는 전달받은 파일이나 URL에서 JD 텍스트를 추출하고 구조화하지만 원본 파일을 영구 저장하지 않는다. Spring은 FastAPI가 반환한 `context_id`와 분석 결과를 사용자 및 지원 세션에 연결한다.

FastAPI의 실행 저장소는 프로젝트 PostgreSQL 안의 `ai_job_contexts`, `ai_analysis_jobs` 테이블을 사용한다. SQLite 구현은 단위 테스트와 로컬 저장소 계약 검증에만 사용한다. 분석 작업이 완료되거나 실패하면 AI 테이블에 임시 저장한 사용자 문서 원문은 제거한다.

지속 대화에서는 Spring이 사용자와 지원 세션의 소유권, 공개 API와 화면용 메시지를 책임진다. FastAPI는 Spring이 저장한 `context_id`, `analysis_id`, `conversation_id` 연결을 전달받아 모델 입력에 사용한 대화 사본을 AI 전용 테이블에 보관한다. FastAPI에는 `user_id`를 전달하지 않는다. 같은 지원 세션인지 추론하지 않고 Spring이 `conversation_id`를 명시한다.

프론트엔드의 사용자 업로드 형식은 PDF·DOCX·TXT로 제한한다. FastAPI의 MD·HTML 처리는 내부 호환 기능으로 유지한다.

## 이유

사용자 인증과 파일 수명은 메인 백엔드의 데이터 책임이다. PDF·DOCX의 텍스트 추출은 JD 분석 전처리이므로 AI 서비스에 두는 편이 분석 파이프라인을 한곳에서 관리하기 쉽다.

## 재검토 조건

- 공용 파일 저장소와 비동기 작업 큐를 도입해 파일 바이트 대신 파일 ID 또는 내부 URL을 전달한다.
- Spring과 FastAPI 사이의 파일 재전송 비용이 운영상 문제가 된다.
- JD 파싱을 다른 서비스에서도 공통으로 사용하게 된다.
- 사용자 대화 원문을 두 서비스에 보관하는 비용이 커져 공용 메시지 저장소나 메시지 조회 API를 도입한다.

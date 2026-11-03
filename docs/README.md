# 문서 목차

저장소의 문서를 찾는 곳입니다. **현행**은 지금 코드를 설명하는 문서이고, **기록**은 작성 당시의 판단과 계획을 남긴 문서입니다. 기록 문서의 수치와 상태는 현재와 다를 수 있습니다.

## 처음 볼 문서

| 문서 | 내용 |
| --- | --- |
| [프로젝트 README](../README.md) | 서비스 소개, 구조, 실행 방법 |
| [infra/README.md](../infra/README.md) | 로컬 실행, 배포, 환경변수 |
| [frontend/README.md](../frontend/README.md) | 프론트엔드 개발 |
| [data/README.md](../data/README.md) | 데이터 파이프라인 |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | 브랜치·커밋·MR 규칙 요약 |

## 현행 문서

### API

| 문서 | 내용 |
| --- | --- |
| [api/supervisor-agent-api.md](api/supervisor-agent-api.md) | 담당을 고르고 결과를 종합하는 supervisor |
| [api/company-analysis-agent.md](api/company-analysis-agent.md) | 기업 분석 담당 |
| [api/position-analysis-api.md](api/position-analysis-api.md) | 포지션 분석 담당 |
| [api/writing-agent-api.md](api/writing-agent-api.md) | 글쓰기 첨삭 담당 |
| [api/jd-coaching-api.md](api/jd-coaching-api.md) | JD 분석·코칭 담당 |
| [../ai/docs/news-trend-agent-api.md](../ai/docs/news-trend-agent-api.md) | 뉴스 담당 |
| [../ai/docs/llm-model-assignment.md](../ai/docs/llm-model-assignment.md) | 담당별 LLM 모델 배정 |

### 설계와 규칙

| 문서 | 내용 |
| --- | --- |
| [design/db-schema.md](design/db-schema.md) | DB 스키마 |
| [conventions/git.md](conventions/git.md) | Git 규칙 |
| [conventions/documentation.md](conventions/documentation.md) | 의사결정 기록 작성법 |
| [../data/docs/DATA_STORAGE_STANDARD.md](../data/docs/DATA_STORAGE_STANDARD.md) | 데이터 저장 기준 |
| [../data/docs/S15P21A504-NEWS-LOAD-PIPELINE.md](../data/docs/S15P21A504-NEWS-LOAD-PIPELINE.md) | 뉴스 적재 경로 |
| [../infra/hadoop/README.md](../infra/hadoop/README.md) | Hadoop·Spark 구성 |
| [../infra/tunnel/README.md](../infra/tunnel/README.md) | vLLM 터널 |

## 의사결정 기록

여러 파트에 걸친 번호 기록과 주제별 기록, 두 곳에 나뉘어 있습니다.

| 문서 | 내용 |
| --- | --- |
| [decisions/0001-missing-data-response.md](decisions/0001-missing-data-response.md) | 결측 응답 방식 |
| [decisions/0002-employee-total-change.md](decisions/0002-employee-total-change.md) | 전사 직원 증감 정의 |
| [decisions/0003-business-report-form-tables-to-sql.md](decisions/0003-business-report-form-tables-to-sql.md) | 사업보고서 서식 표의 SQL 저장 |
| [../Decisions/_index.md](../Decisions/_index.md) | 제품·아키텍처·AI 주제별 결정 목록 |
| [../data/docs/S15P21A504-DECISIONS-0916.md](../data/docs/S15P21A504-DECISIONS-0916.md) | 데이터 파트 결정 요청 8건 |

## 기록 문서

### AI

| 위치 | 내용 |
| --- | --- |
| [../ai/docs/](../ai/docs/) | 제품 가치, 기능 계약, 평가 계획, JD 기준선 결과 |
| [experiments/](experiments/) | 기업 검색 평가셋, 서식 표 검수 실험 |
| [handoff/](handoff/) | 기업 분석 담당 인수인계와 알려진 문제 |
| [superpowers/](superpowers/) | AI 에이전트 기능의 설계(specs)와 구현 계획(plans) |

### 데이터

| 위치 | 내용 |
| --- | --- |
| [../data/docs/HANDOFF.md](../data/docs/HANDOFF.md) | 초기 파이프라인 인수인계 |
| [../data/docs/DESIGN.md](../data/docs/DESIGN.md) | 파이프라인 설계 |
| [../data/docs/API_NOTES.md](../data/docs/API_NOTES.md) | OpenDART API 실측 기록 |
| [../data/docs/COMPARISON_RULES.md](../data/docs/COMPARISON_RULES.md) | 비교 대상 선정 규칙 |
| [../data/docs/news-poc/](../data/docs/news-poc/) | 뉴스 PoC 조사와 판정 |
| [../data/docs/](../data/docs/) | 이슈별 작업 지시, 설계, 회신(`S15P21A504-*`), 백로그와 작업 계획 |

### 프론트엔드

| 위치 | 내용 |
| --- | --- |
| [../frontend/docs/work-split.md](../frontend/docs/work-split.md) | 초기 작업 분담 |
| [../frontend/docs/superpowers/](../frontend/docs/superpowers/) | 기업 상세·랜딩 화면 설계와 구현 계획 |

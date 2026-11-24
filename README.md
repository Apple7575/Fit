# Fit

기업의 눈으로 보는 나의 Fit. 취업 준비생이 공시 데이터를 근거로 기업을 분석하고, 자기소개서와 면접을 AI와 준비하는 서비스입니다.

SSAFY 15기 특화 프로젝트(빅데이터 분산 트랙, 서울 5반 A504) 결과물이며, 프로젝트는 종료되었습니다. 개발 기간은 2026-08-24부터 2026-10-13까지입니다.

## 주요 기능

| 기능 | 내용 |
| --- | --- |
| 기업 분석 | 기업 검색, 요약, 핵심 지표, 재무 추이, 성장 분석, 동일 산업 비교, 집중 분야, 최근 이슈 |
| 자기소개서 리뷰 | 자기소개서 작성과 메신저 형식의 AI 담당자 첨삭 |
| AI 면접 | 질문·꼬리질문 생성, 답변 분석, MediaPipe 기반 시선·머리 자세 분석 |

기업 데이터는 OpenDART 공시와 Google News RSS에서 수집합니다. 기업 시드는 상장사 2,662개사입니다.

## 구조

```
브라우저 → nginx ─┬─ /      → frontend  (React)
                  └─ /api/  → backend   (Spring Boot) ─┬→ PostgreSQL
                                                       ├→ LLM (면접 기능)
                                                       └→ ai (FastAPI) ─┬→ PostgreSQL
                                                                        └→ LLM
```

AI 서버는 외부에 열지 않고, 프록시에서 `/ai/` 경로를 차단합니다. AI 호출은 Spring을 거칩니다.

| 폴더 | 내용 | 기술 |
| --- | --- | --- |
| [`frontend/`](frontend/README.md) | 웹 화면 | React 19, Vite 8, TypeScript 6, Tailwind CSS 4 |
| `backend/` | 인증, 권한, 저장, API | Java 21, Spring Boot 4.1, JPA, Flyway |
| `ai/` | 에이전트 6종과 RAG | Python 3.12, FastAPI, LangGraph |
| [`data/`](data/README.md) | 수집·정규화·적재 파이프라인 | Python, Hadoop, Spark |
| [`infra/`](infra/README.md) | 배포와 운영 구성 | Docker Compose, nginx, Jenkins, PostgreSQL 18 |
| [`docs/`](docs/README.md) | 저장소 전체 문서 목차 | |

## 로컬에서 보기

### 화면 데모

Node.js 24에서 프론트엔드를 실행한 뒤 `http://localhost:5173`에 접속합니다. 기본 개발 모드는 mock 데이터를 사용합니다.

```bash
cd frontend
npm ci
npm run dev
```

### 전체 스택

Docker Compose가 실행 중인 상태에서 저장소 루트의 아래 명령을 Bash로 실행한 뒤 `http://localhost:3000`에 접속합니다. Windows에서는 Git Bash 또는 WSL을 사용할 수 있습니다.

```bash
./infra/local.sh
```

처음 실행하기 전에 `infra/.env.local`을 만들고 아래 내용을 입력합니다. 비밀번호 예시는 로컬 실행 전용입니다.

```dotenv
ENV_NAME=local
COMPOSE_PROJECT_NAME=ca-local
TAG=local
POSTGRES_PASSWORD=fit-local-dev
AI_ROOT_PATH=
AI_INTERVIEW_PROVIDER=gms
VLLM_BASE_URL=http://host.docker.internal:8000
```

로컬 DB에는 기업 데이터가 없으므로 검색 결과가 비어 있을 수 있습니다. AI 연동과 데이터 적재 방법은 [인프라 문서](infra/README.md)와 [데이터 문서](data/README.md)를 참고하세요. 이 공개 저장소에서는 `.env`와 `.env.*` 파일을 로컬에서 작성합니다. Vite에서 실제 API를 호출하려면 `frontend/.env.api`에 `VITE_API_MOCK=false`를 설정하고 `npm run dev:api`를 실행합니다.

## 테스트

```bash
cd frontend && npm run test -- --run          # 프론트엔드
cd backend && ./gradlew test                  # 백엔드
python -m unittest discover -s ai/tests -t .  # AI (저장소 루트에서 실행)
```

## 문서

- [문서 목차](docs/README.md)
- [GitHub 이전 가이드](docs/github-migration.md)
- [개발 당시 기여 규칙](CONTRIBUTING.md)

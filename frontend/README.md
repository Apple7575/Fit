# 기업 변화 분석 서비스 Frontend

DART의 재무·사업·인력·투자 데이터를 바탕으로 기업의 최근 변화를 보여주는 취업 준비생용 기업분석 서비스의 프론트엔드입니다.

현재 1차 MVP에서는 기업 검색 홈과 기업 상세 화면을 위한 프로젝트 구조 및 라우팅 기반을 제공합니다. 기업 검색, 지표 카드, 5개년 그래프, 동일 산업 비교 기능은 이후 단계에서 추가합니다.

## 기술 스택

| 구분 | 기술 | 버전 |
| --- | --- | --- |
| UI | React | 19.2.8 |
| 빌드 도구 | Vite | 8.2.2 |
| 언어 | TypeScript | 6.0.3 |
| 라우팅 | React Router | 7.18.2 |
| 테스트 | Vitest, Testing Library | 4.1.11, 16.3.2 |
| 정적 분석 | OxcLint | 1.79.0 |

## 실행 환경

- Node.js `^20.19.0` 또는 `>=22.12.0`
- npm

현재 개발 환경에서 확인한 버전은 Node.js `24.18.0`, npm `11.16.0`입니다.

## 시작하기

저장소를 받은 뒤 `frontend` 디렉터리에서 진행합니다.

```bash
cd frontend
npm ci
npm run dev
```

개발 서버가 실행되면 터미널에 출력된 로컬 주소로 접속합니다. Vite의 기본 주소는 일반적으로 `http://localhost:5173`입니다.

`package-lock.json`이 없는 초기 환경에서만 `npm install`을 사용합니다. 팀원이 동일한 버전의 패키지를 설치할 때는 `npm ci`를 권장합니다.

## 주요 명령어

| 명령어 | 설명 |
| --- | --- |
| `npm run dev` | Vite 개발 서버를 실행합니다. |
| `npm run test -- --run` | 전체 테스트를 한 번 실행하고 종료합니다. |
| `npm run test` | 테스트를 감시 모드로 실행합니다. |
| `npm run lint` | OxcLint로 코드를 검사합니다. |
| `npm run build` | TypeScript 검사 후 배포 파일을 생성합니다. |
| `npm run preview` | 빌드된 결과를 로컬에서 확인합니다. |

기능 작업을 마치기 전에는 최소한 다음 명령을 모두 확인합니다.

```bash
npm run test -- --run
npm run lint
npm run build
```

## 현재 라우팅

| URL | 페이지 | 설명 |
| --- | --- | --- |
| `/` | `HomePage` | 기업 검색이 들어갈 홈 화면 |
| `/companies/:companyId` | `CompanyDetailPage` | 선택한 기업의 상세 분석 화면 |
| 그 외 주소 | `NotFoundPage` | 404 안내 화면 |

기업 상세 주소에는 기업명이 아닌 고유 식별자를 사용합니다.

```text
/companies/005930
```

## 폴더 구조

```text
frontend/
├─ public/                       # 빌드 시 그대로 제공되는 정적 파일
├─ src/
│  ├─ app/                       # 앱 최상위 구성과 라우팅
│  │  ├─ App.tsx
│  │  ├─ router.tsx
│  │  └─ router.test.tsx
│  ├─ pages/                     # URL 단위 화면
│  │  ├─ home/
│  │  ├─ company-detail/
│  │  └─ not-found/
│  ├─ features/
│  │  └─ company-search/         # 기업 검색 기능 영역
│  ├─ components/
│  │  ├─ common/                 # 여러 화면에서 사용하는 공통 UI
│  │  └─ layout/                 # 헤더 등 공통 화면 골격
│  ├─ mocks/                     # API 연결 전 사용할 목업 데이터
│  ├─ types/                     # 공통 TypeScript 타입
│  ├─ styles/
│  │  └─ global.css              # 전역 스타일
│  ├─ test/
│  │  └─ setup.ts                # 테스트 공통 설정
│  └─ main.tsx                   # React 실행 진입점
├─ index.html
├─ package.json
├─ package-lock.json
├─ vite.config.ts
├─ .oxlintrc.json                # OxcLint 규칙
├─ Dockerfile                    # 프론트 빌드 및 Nginx 배포 이미지
├─ nginx.conf                    # SPA 라우팅을 지원하는 Nginx 설정
└─ tsconfig*.json
```

현재 비어 있는 확장용 디렉터리는 `.gitkeep`으로 유지합니다. 실제 파일이 추가되면 해당 `.gitkeep`은 제거할 수 있습니다.

## 애플리케이션 실행 흐름

```text
index.html
→ src/main.tsx
→ src/app/App.tsx
→ src/app/router.tsx
→ 현재 URL에 해당하는 페이지
```

페이지는 URL 단위 화면을 구성하고, 사용자 행동 중심 코드는 `features`, 여러 화면에서 반복 사용하는 UI는 `components`에 배치합니다.

## 1차 MVP 화면 계획

### 홈 화면

- 화면 중앙 기업 검색창
- 기업명 자동완성
- 기업 선택 후 상세 페이지 이동

### 기업 상세 화면

- 기업명 및 기본 정보
- 2025년 핵심 지표
  - 매출액
  - 영업이익
  - 직원 수
  - 1인 평균 급여
  - 평균 근속연수
  - 매출 대비 R&D 비율
- 2021~2025년 지표 변화 시각화
- 2025년 동일 산업 기업 비교

위 기능은 현재 라우팅 다음 단계의 개발 범위이며 아직 구현되지 않았습니다.

## 환경변수

로컬 환경변수는 `.env` 파일에서 관리하며 저장소에 커밋하지 않습니다. 팀 공유가 필요한 환경변수 이름은 값 없이 `.env.example`에 작성합니다.

Vite에서 `VITE_`로 시작하는 환경변수는 브라우저 번들에 포함될 수 있으므로 비밀번호, API 비밀키, 인증서 등의 민감정보를 넣으면 안 됩니다.

```env
VITE_API_BASE_URL=http://localhost:8080
```

환경변수가 실제로 필요해지는 API 연결 단계에서 `.env.example`을 추가합니다.

## Docker 실행

`Dockerfile`은 Node.js에서 프론트를 빌드한 뒤 Nginx로 정적 파일을 제공하는 멀티 스테이지 이미지입니다.

```bash
docker build -t company-analysis-frontend .
docker run --rm -p 8080:80 company-analysis-frontend
```

컨테이너 실행 후 `http://localhost:8080`에서 확인할 수 있습니다. `nginx.conf`는 새로고침 시에도 React Router 경로가 `index.html`로 연결되도록 설정되어 있습니다.

## 개발 시 주의사항

- `src` 내부 파일을 중심으로 작업합니다.
- `node_modules`는 npm이 관리하므로 직접 수정하거나 커밋하지 않습니다.
- `dist`는 `npm run build`가 생성하는 결과물이므로 직접 수정하거나 커밋하지 않습니다.
- 새 페이지를 추가하면 `src/app/router.tsx`에 라우트를 등록합니다.
- 라우팅이나 사용자 동작을 변경할 때는 관련 테스트를 함께 수정합니다.
- 커밋과 브랜치 이름은 팀에서 합의한 규칙을 따릅니다.

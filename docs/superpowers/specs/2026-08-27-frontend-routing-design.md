# 프론트엔드 라우팅 초기 구조 설계

## 목표

비어 있는 `frontend` 디렉터리에 React, Vite, TypeScript 기반의 최소 실행 환경을 만들고, 홈·기업 상세·404 화면을 URL로 구분한다. 이후 기업 검색과 분석 기능을 추가할 때 라우팅 및 폴더 구조를 다시 설계하지 않아도 되는 기반을 제공한다.

## 범위

- `/`: 기업 검색이 들어갈 홈 화면
- `/companies/:companyId`: 기업 고유 식별자를 사용하는 상세 화면
- `*`: 존재하지 않는 주소를 처리하는 404 화면
- 각 페이지는 현재 라우팅 확인용 최소 문구만 표시한다.
- 기업 검색, 차트, API 호출, 목업 기업 데이터는 이번 작업에서 제외한다.

## 기술 구성

- React 19.2.8
- Vite 8.2.2
- TypeScript 6.0.3
- React Router
- Vitest, Testing Library, jsdom
- npm

## 디렉터리 구조

```text
frontend/
├─ src/
│  ├─ app/
│  │  ├─ App.tsx
│  │  └─ router.tsx
│  ├─ pages/
│  │  ├─ home/HomePage.tsx
│  │  ├─ company-detail/CompanyDetailPage.tsx
│  │  └─ not-found/NotFoundPage.tsx
│  ├─ features/company-search/
│  ├─ components/common/
│  ├─ components/layout/
│  ├─ mocks/
│  ├─ types/
│  ├─ styles/global.css
│  ├─ test/setup.ts
│  └─ main.tsx
├─ index.html
├─ package.json
├─ tsconfig.json
├─ tsconfig.app.json
├─ tsconfig.node.json
└─ vite.config.ts
```

확장용 빈 폴더는 `.gitkeep`으로 유지하고, 실제 기능이 추가되면 유지 파일을 제거한다.

## 책임 분리

- `main.tsx`: 브라우저 DOM에 애플리케이션을 마운트한다.
- `App.tsx`: 앱 최상위 진입점이며 라우터를 제공한다.
- `router.tsx`: URL과 페이지 컴포넌트의 매핑만 관리한다.
- `pages`: URL 단위 화면을 담당한다.
- `features`: 검색처럼 사용자 행동 중심 기능을 담당한다.
- `components`: 여러 기능과 페이지에서 재사용하는 UI를 담당한다.
- `mocks`, `types`: 후속 기업 분석 화면에서 사용할 목업 데이터와 공통 타입을 담당한다.

## 라우팅 동작

- 사용자가 `/`에 접근하면 홈 제목을 확인할 수 있다.
- 사용자가 `/companies/005930`에 접근하면 상세 페이지에서 `005930`을 확인할 수 있다.
- 사용자가 정의되지 않은 주소에 접근하면 404 안내와 홈 이동 링크를 확인할 수 있다.

## 오류 처리

잘못된 URL은 404 페이지로 처리한다. `companyId`의 실제 존재 여부 검증은 기업 API 연결 단계에서 추가하며 이번 범위에서는 문자열 경로 매개변수로만 취급한다.

## 검증

- Memory Router 기반 테스트로 세 경로가 올바른 페이지를 렌더링하는지 확인한다.
- TypeScript 검사와 Vite 프로덕션 빌드가 성공하는지 확인한다.
- ESLint를 실행해 초기 코드에 정적 분석 오류가 없는지 확인한다.

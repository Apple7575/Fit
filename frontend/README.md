# Fit Frontend

Fit의 웹 화면입니다. 기업 분석, 자기소개서 리뷰, AI 면접을 제공합니다.

## 기술 스택

React 19, React Router 7, Vite 8, TypeScript 6, Tailwind CSS 4, Vitest, Testing Library, oxlint, MediaPipe Tasks Vision

## 시작하기

Node.js `^20.19.0` 또는 `>=22.12.0`이 필요합니다. CI는 Node 24를 사용합니다.

```bash
cd frontend
npm ci
npm run dev
```

## 명령어

| 명령어 | 설명 |
| --- | --- |
| `npm run dev` | 백엔드 없이 mock 데이터로 실행 (`:5173`) |
| `npm run dev:api` | 실제 API로 실행. 백엔드가 먼저 떠 있어야 함 |
| `npm run test -- --run` | 테스트 1회 실행 |
| `npm run lint` | oxlint 검사 |
| `npm run build` | 타입 검사 후 배포 파일 생성 |
| `npm run preview` | 빌드 결과 확인 |

`npm run dev:api`에 쓸 백엔드는 `./infra/local.sh front`로 띄웁니다. 자세한 내용은 [infra/README.md](../infra/README.md)에 있습니다.

## 화면

| 경로 | 화면 |
| --- | --- |
| `/` | 홈 |
| `/companies` | 기업 검색 |
| `/companies/:companyId/overview` | 기업 상세. 옛 구획 주소는 이 화면의 해시로 이동 |
| `/cover-letters`, `/cover-letters/new`, `/cover-letters/:id` | 자기소개서 목록, 작성, 조회 |
| `/cover-letters/:id/review` | 자기소개서 리뷰 룸 목록 |
| `/agent-rooms/:roomId` | 리뷰 룸 대화 |
| `/interviews`, `/interviews/new`, `/interviews/:id` | AI 면접 목록, 진행, 조회 |
| `/login`, `/signup`, `/verify-sent`, `/verify` | 인증 |
| `/mypage` | 마이페이지 |

라우트는 `src/app/router.tsx`에 등록합니다.

## 폴더 구조

```
src/
├── app/         라우터
├── pages/       경로별 화면
├── features/    기능 단위 코드 (기업 분석, 자기소개서, 면접, 인증 등)
├── components/  공용 컴포넌트 (brand, charts, common, layout)
├── api/         API 호출 공통 코드
├── mocks/       mock 데이터
├── hooks/  styles/  types/  utils/  test/
public/
├── company-media/    기업 사진·로고 자료
└── interview-guide/  면접 안내 자료
```

## 환경변수

`.env.example`을 `.env.development.local`로 복사해 사용합니다.

| 변수 | 설명 |
| --- | --- |
| `VITE_API_BASE_URL` | 백엔드 오리진. 비우면 같은 오리진의 `/api` 호출 |
| `VITE_API_MOCK` | `true`면 mock, `false`면 실제 API. 없으면 `npm run dev`는 mock, 빌드본은 실제 API |
| `VITE_LOGO_DEV_KEY` | logo.dev 퍼블리셔블 키. 없으면 파비콘, 이니셜 아바타 순으로 대체 |

## 배포

`Dockerfile`은 프론트를 빌드한 뒤 nginx로 정적 파일을 제공합니다. `nginx.conf`는 새로고침 시에도 React Router 경로가 `index.html`로 연결되도록 설정합니다. 배포 흐름은 [infra/README.md](../infra/README.md)를 참고하세요.

CI는 lint와 build만 실행하므로, 테스트는 로컬에서 직접 실행해야 합니다.

# 프론트엔드 작업 분담 (기능 단위)

기준: Jira MVP 백로그(US-01~04) + 기업분석 API 명세서(엔드포인트 8개).
페이지 단위가 아닌 **기능(feature) 단위 vertical slice**로 나눈다. 한 사람이 한 기능의 mock → API 호출 → 상태 → UI → 테스트까지 책임진다.

## 1. API ↔ 기능 매핑

| # | 엔드포인트 | 우선순위 | 파라미터 | 응답 | 사용 기능 |
| --- | --- | --- | --- | --- | --- |
| 1 | `GET /api/companies` | P0 | `keyword`(필수), `page`, `size` | `items[]` (없으면 빈 배열) | 기업 검색 |
| 2 | `GET /api/companies/{corpCode}` | P1 | - | 기업 상세 | 상세 헤더 |
| 3 | `GET /api/companies/{corpCode}/metrics` | P0 | `year`, `yoy` | `metrics[6]` | 핵심지표 카드 |
| 4 | `GET /api/companies/{corpCode}/metrics/{metric}` | P2 | `year`, `yoy` | 지표 1개 | (MVP 미사용) |
| 5 | `GET /api/companies/{corpCode}/metrics/timeseries` | P0 | `from`, `to`, `keys` | `series[6] × points[5]` | 변화 그래프 |
| 6 | `GET /api/companies/{corpCode}/metrics/{metric}/timeseries` | P2 | `from`, `to` | `points[5]` | (MVP 미사용) |
| 7 | `GET /api/companies/{corpCode}/industry-comparison` | P1 | `year`(기본 2025) | `companies[]` (`isTarget`) | 산업 비교 |
| 8 | `GET /api/companies/{corpCode}/metrics/{metric}/industry-comparison` | P2 | `metric`, `year` | `companies[]` | (MVP 미사용) |

에러: `400 INVALID_PARAMETER`, `400 METRIC_NOT_SUPPORTED`, `404 COMPANY_NOT_FOUND`.
MVP는 P0·P1(1·2·3·5·7)만 사용한다. 개별 지표 API(4·6·8)는 통합 응답을 프론트에서 필터링하면 되므로 쓰지 않는다.

## 2. 분담

### 0단계 — 공통 기반 (먼저, 반나절)

한 명이 아래를 만드는 동안 다른 한 명은 mock JSON을 작성한다.

| 항목 | 위치 | 비고 |
| --- | --- | --- |
| API 클라이언트 | `src/api/client.ts` | fetch 래퍼, `VITE_API_BASE_URL` env 분리, 공통 에러 타입(`ApiError { status, code }`) |
| 공통 상태 컴포넌트 | `src/components/common/` | `LoadingState`, `ErrorState`, `EmptyState` |
| 금액 포맷 유틸 | `src/utils/formatAmount.ts` | 원 → 억/조 단위, `null` → "미제공" |
| Mock 응답 | `src/mocks/*.json` | 명세서 응답 예시를 그대로 옮김. 백엔드 완성 전까지 이걸로 개발 |
| 정리 | - | 홈/404 h1 스타일(Tailwind Preflight로 깨짐) 복구, `@/` alias |

### A — 검색 + 핵심지표 카드

Jira: F-01, F-02, F-05, F-10, F-11 (5개)

| 기능 | 폴더 | API | 주요 AC |
| --- | --- | --- | --- |
| 기업 검색 | `src/features/company-search/` | #1 | 앞뒤 공백 제거, 빈 값 요청 금지, Enter=버튼, 로딩 중 중복 요청 방지, 빈 결과/오류 구분 |
| 상세 헤더 | `src/features/company-header/` | #2 | 기업명·산업·기업코드·기준연도 표시 |
| 핵심지표 카드 | `src/features/key-metrics/` | #3 | 6개 카드 명칭·값 대응, 단위·기준연도 표시, 누락은 "미제공", corpCode 변경 시 재조회 |

### B — 변화 그래프 + 산업 비교

Jira: F-15, F-16, F-17, F-21, F-22, F-23 (6개)

| 기능 | 폴더 | API | 주요 AC |
| --- | --- | --- | --- |
| 변화 그래프 | `src/features/financial-trend/` | #5 | X축 2021~2025, 툴팁, 지표 선택 시 즉시 갱신, 누락 연도 허용, 영역 밖 넘침 금지 |
| 산업 비교 | `src/features/industry-comparison/` | #7 | 선택 기업(`isTarget`) 강조, 지표 변경·정렬(오름/내림), 비교 대상 부족 안내, 긴 기업명·큰 금액 레이아웃 유지 |
| 지표 선택 UI | `src/components/common/MetricSelector.tsx` | - | 그래프·비교 공용. B가 만든다 |

차트 라이브러리 선정(Recharts 권장)도 B 담당.

## 3. 충돌 방지 규칙

1. `pages/company-detail/CompanyDetailPage.tsx`는 **조립만** 한다. 각 feature는 `export function XxxSection({ corpCode })` 하나를 내보내고, 페이지엔 그 한 줄만 추가한다.
2. 자기 `features/<이름>/` 폴더 밖은 건드리지 않는다. 공통 컴포넌트가 필요하면 상대에게 말하고 `components/common/`에 추가한다.
3. 각 feature 폴더 구조는 통일한다.
   ```
   features/<name>/
   ├─ api.ts          # client.ts 사용, 응답 타입 정의
   ├─ types.ts
   ├─ useXxx.ts       # 데이터 훅 (loading / error / data)
   ├─ XxxSection.tsx  # 페이지에 꽂는 진입 컴포넌트
   ├─ components/     # 내부 UI
   └─ Xxx.test.tsx
   ```
4. 브랜치는 feature 단위로: `feature/S15P21A504-<이슈>-company-search` 등. MR은 develop으로, 리뷰어는 서로.

## 4. 시작 전 확정 필요

- **`{metric}` 키 이름 6개** — 명세서에 `keys` 파라미터·`metrics[6]`만 있고 실제 키(`revenue`, `operating_profit`…)가 없다. mock 작성 전에 백엔드와 합의.
- ~~**핵심지표 6개 정의 불일치**~~ → **명세서 기준으로 확정 (2026-08-28)**: 매출액·영업이익·직원 수·1인 평균 급여·평균 근속·R&D/매출. 프론트 키: `revenue, operating_profit, employee_count, avg_salary, avg_tenure, rd_ratio` (`src/types/metrics.ts`). 단위는 원/원/명/원/년/% — 백엔드 응답 키와 단위(%는 8.3 처럼 퍼센트 값 그대로) 합의 필요.
- **산업 비교 범위** — KSIC 대분류(2자리) vs 중분류, 비교 대상 수(상위 N), 기본 정렬 기준.
- **`yoy` 응답 형태** — 전년 대비 증감을 값으로 주는지 비율로 주는지.

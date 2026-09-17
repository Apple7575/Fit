# 기업소개(기업 개요) 화면 설계 — S15P21A504-77

2026-09-02 · 담당: 장수철(Frontend)

## 목표

취준생이 "이 회사가 어떤 회사인지" 빠르게 확인하는 기업 개요 탭을 만든다.
기존 기업 상세 페이지를 탭 구조로 재편하고, 첫 탭으로 기업 개요를 구현한다.

## 범위

### 이번 티켓에서 하는 것

- `/companies/:companyId` 를 탭 레이아웃으로 재편 (헤더 + 탭 네비 + Outlet)
- 상단 헤더: 브레드크럼(홈 > 기업 분석 > {기업명}) + 기업명 검색바 + 탭 버튼
- 탭 구성
  - **기업 개요** `/companies/:id/overview` — 신규 (이 티켓의 본체)
  - **산업 비교** `/companies/:id/comparison` — 기존 IndustryComparisonSection 이동
  - **성장 분석 · 집중 분야 · 최근 이슈** — 비활성(disabled) 버튼으로만 표시
- `/companies/:id` 진입 시 `/overview` 로 리다이렉트 → 기존 검색 연결 유지
- 기업 개요 탭 내용
  - 기본정보 카드: 로고 플레이스홀더(이니셜) + 기업명 + 업종·대표자·설립일·주소·홈페이지
  - 조건부 섹션 4종: 주요 사업 / 사업부 / 주요 제품 / 사업부 매출(도넛)
  - 우상단 "데이터 기준: {dataYear}" 칩
- 결측 상태 처리 (아래 규칙 참고)

### 이번 티켓에서 하지 않는 것

- 로그인·관심기업·알림·즐겨찾기 별 (인증 없음)
- 기업 한 줄 소개(태그라인) — 데이터 출처 없음
- 사업부 풀네임·설명문·"자세히 보기" — API 가 code 만 제공
- 주요 사업·제품의 항목별 아이콘·설명 — API 가 문자열 배열만 제공
- 성장 분석 탭 화면 — 기존 핵심지표·재무추이 섹션은 **코드와 테스트를 그대로 두고
  화면에서만 제외**한다. 성장 분석 티켓에서 탭에 붙인다.
- 왼쪽 사이드바 — 탭 버튼이 대체한다.

## 데이터 계약

### GET /api/companies/{corpCode} (v2)

기본정보 카드의 유일한 출처. v2 에서 `address` · `homepageUrl` · `dataYear` 가 추가된다.

- **현재 백엔드는 v2 미구현**(DB 에 주소·홈페이지 컬럼 없음). 백엔드 작업이 선행 협업 대상.
- 프론트 `CompanyDetail` 타입에 세 필드를 nullable 로 추가한다.
  응답에 필드가 없거나 null 이면 결측 처리로 자연스럽게 동작한다.

### GET /api/companies/{corpCode}/profile (P1, 신규)

조건부 섹션 4종의 유일한 출처.

```
data: {
  year: number,
  businesses: string[],          // 주요 사업
  segments: [{ code, revenue, revenueShare }],  // 사업부 + 사업부 매출
  totalRevenue: number,
  products: string[]             // 주요 제품
}
```

## 결측 처리 규칙 (Done: 데이터 없음 상태 처리)

| 상황 | 처리 |
|---|---|
| 기본정보 개별 필드 null | 해당 필드에 "정보 없음" 표시. 카드 유지 |
| `dataYear` null/부재 | 기준연도 칩 미표시 |
| profile 의 개별 배열 empty/null | 해당 섹션 카드만 미노출 |
| profile 404 또는 전 배열 empty | 조건부 영역 전체 미노출 (기본정보 카드만 남음) |
| profile 5xx | 조건부 영역에 InlineNotice 오류 표시 (기본정보는 별개 요청이라 유지) |
| segment.revenue null (미공시) | 도넛에서 제외, 리스트에 "미공시" 표시 |
| 기본정보 404 | 기존 CompanyDetailPage 의 F-31 규칙 유지 (일반 문구로 대체) |

## 구조

기존 feature 폴더 패턴(`api.ts` + `use<Name>.ts` + 섹션 컴포넌트 + mock + 테스트)을 따른다.

```
features/company-profile/
  api.ts                    # fetchCompanyProfile (VITE_API_MOCK 규칙 동일)
  useCompanyProfile.ts      # useApiQuery 래핑
  CompanyProfileSections.tsx  # profile 1회 조회 → 조건부 카드 4종 분배
  BusinessCard.tsx          # 주요 사업 (이름 카드 그리드)
  SegmentCard.tsx           # 사업부 (code + 매출·비중)
  ProductCard.tsx           # 주요 제품 (이름 배지)
  SegmentRevenueCard.tsx    # 사업부 매출 (SVG 도넛 + 리스트)
  types.ts

features/company-detail/    # CompanyDetail 타입에 address·homepageUrl·dataYear 추가
components/layout/          # AppHeader 확장: 브레드크럼·검색바·탭 네비
pages/company-detail/
  CompanyDetailPage.tsx     # 레이아웃 (헤더 + 탭 + Outlet) 로 재편
  CompanyOverviewTab.tsx    # 기본정보 카드 + CompanyProfileSections
  CompanyComparisonTab.tsx  # 기존 IndustryComparisonSection 재배치
mocks/companyProfile.ts     # 삼성전자형 풀데이터 + 결측 케이스 기업
```

- 도넛 차트는 라이브러리 추가 없이 순수 SVG(stroke-dasharray) 로 그린다.
- 헤더 검색바는 기존 CompanySearchForm 을 재사용하되, 선택 시
  `/companies/{corpCode}/overview` 로 이동하는 콜백만 다르게 준다.
- 탭 버튼: NavLink 로 활성 탭 하이라이트. 비활성 3종은 `disabled` + "준비 중" 툴팁.

## 테스트

기존 vitest + RTL 패턴.

- api.ts: mock/실 API 분기, 404 → ApiError
- CompanyOverviewTab: 기본정보 렌더, 필드 null → "정보 없음", dataYear 칩 유무
- CompanyProfileSections: 배열 empty → 카드 미노출, 전체 empty → 영역 미노출, 5xx → 오류 표시
- SegmentRevenueCard: revenue null 부문 제외·"미공시" 표시, 비중 합계 렌더
- router: `/companies/:id` → overview 리다이렉트, comparison 탭 라우팅

# 산업 비교 화면 v2 설계 — S15P21A504-80

2026-09-02 · 담당: 장수철(Frontend) · 서브태스크 107(화면 구성), 108(API·결측)

## 목표

관심 기업이 같은 산업의 다른 기업보다 어떤 위치인지 확인한다. 기존 산업 비교 섹션을
API v2(사용자가 고른 peers 비교)에 맞추고 Jira 기본 비교 10종 UI를 준비한다.

## 범위

- 비교 지표 10종 UI (Jira 80): 매출·매출 성장률·영업이익·영업이익률·순이익·부채비율·직원 수·직원 증가율·평균 급여·평균 근속.
  API v2 가 주는 것은 7종(revenue, revenue_growth, operating_profit, operating_margin, employee_count, average_salary, rd_ratio)이라
  순이익·부채비율·직원 증가율·평균 근속은 값이 올 때까지 "미제공"으로 표시하고 선택지에 힌트를 단다.
- 비교 기업 선택: `GET /api/industries/{industryCode}/companies` 후보에서 최대 3곳(peers). 조회 기업 자신은 제외.
  후보가 도착하면 매출순 상위 3곳을 자동 선택하고, 사용자가 바꾸면 재조회.
- 기업별 막대 그래프(선택 지표) + 기업 × 10지표 전체 표. 조회 기업 강조(막대·표 첫 행).
- 결측: null → "미제공"(0 아님), 음수는 손실 색, 선택 지표가 응답 metrics 에 없으면 안내 문구.

## 데이터 계약

- `GET /api/companies/{corpCode}/industry-comparison?peers=a,b,c` (v2). year·metrics 파라미터는 보내지 않는다
  (기준연도는 서버, 지표는 서버 기본 7종). 대상 기업은 값이 없어도 항상 포함(isTarget).
- `GET /api/industries/{industryCode}/companies?sort=revenue&limit=50` → companies[]. 없는 industryCode 는 빈 배열 200.
- industryCode 는 기업 기본정보(`/api/companies/{corpCode}`)의 industryCode 를 탭이 넘긴다.

## 흐름과 이중 호출 방지

1. 탭: 기본정보 로딩 중이면 자리만 잡는다. 성공하면 industryCode 를 섹션에 넘긴다(실패 시 null).
2. 섹션: industryCode 가 있으면 후보를 먼저 불러오고, 도착할 때까지 비교를 조회하지 않는다.
3. 후보 도착 → 상위 3곳 자동 선택 → 비교 1회 조회. 이후 선택 변경마다 재조회(진행 중 요청은 취소).
4. industryCode 가 없으면 peers 없이 바로 조회(대상 기업만).

## 구조

```
features/industry-comparison/
  types.ts                  COMPARISON_METRIC_KEYS(10) · 라벨·단위 · MAX_PEERS · IndustryCompany
  api.ts                    fetchIndustryComparison(peers) · fetchIndustryCompanies
  useIndustryComparison.ts  peers 정렬 키
  useIndustryCompanies.ts   후보 (industryCode null 이면 빈 목록)
  PeerSelector.tsx          체크박스, 최대 3
  ComparisonTable.tsx       기업 × 10지표 표
  IndustryComparisonSection.tsx  섹션 셸 → ComparisonBody(peers 상태) → IndustryComparisonView
components/common/PillRadioGroup.tsx  범용 pill 라디오 (힌트 지원)
pages/company-detail/CompanyComparisonTab.tsx  industryCode 전달
mocks/industryComparison.ts  v2 값 + 후보 목록
```

핵심지표 카탈로그(`types/metrics.ts`)는 건드리지 않는다 — 비교 지표는 독립 정의.

## 테스트

- View: 10종 선택지·미제공 힌트·미지원 지표 선택 시 안내·비율 단위·표 구조(조회 기업 첫 행, 미제공 4칸)
- Section: industryCode 없으면 peers 없이 1회 조회 / 후보 대기 후 상위 3곳 peers 로 1회 조회 / 선택 변경 시 재조회·3개 상한 / 404·재시도·모르는 키 제거

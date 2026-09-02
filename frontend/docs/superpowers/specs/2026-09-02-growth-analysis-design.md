# 성장 분석 화면 설계 — S15P21A504-78

2026-09-02 · 담당: 장수철(Frontend) · 서브태스크 103(화면 구성), 104(지표 선택·API·결측)

## 목표

기업이 최근 5년간 성장하고 있는지 주요 수치로 확인하는 "성장 분석" 탭.

## 범위

- `/companies/:id/growth` 탭 활성화 (CompanyTabNav · router)
- 탭 내용 = 기준연도 핵심지표 섹션 + 최근 5개년 변화 그래프 섹션 (기존 컴포넌트 재배치·보강)
- 표시 지표 6종(Jira 표시 항목 = `/metrics` v2): 매출·영업이익·당기순이익·직원 수·평균 급여·평균 근속
- "주요 증가율/비율": 지표별 전년 대비 증감률(yoy.changeRate) 배지 + profitability 블록(영업이익률·순이익률·부채비율)
- 5년 그래프: 지표 선택(기존) + 연도별 전년 대비 증감률 스트립 + 툴팁에 증감률
- 결측 연도: 값 null 은 선을 끊고 마커 없이, 표에는 "미제공"; 증감률 null 은 "–"

## 데이터 계약

- `GET /api/companies/{corpCode}/metrics?year=` (v2): metrics[6] (net_income 추가·rd_ratio 제외) + yoy + profitability.
  year 는 기업 기본정보의 dataYear 를 넘기고, 없으면 생략해 서버 기본(최신)을 쓴다.
- `GET /api/companies/{corpCode}/metrics/timeseries?from=2021&to=2025` (v2): points[].changeRate 추가.
- 응답에 없는 필드는 null 로 정규화. 모르는 지표 키는 무시.

## 지표 카탈로그 변경

- `METRIC_KEYS`(카탈로그)에 `net_income` 추가. `rd_ratio` 는 산업 비교가 아직 쓰므로 카탈로그에 유지.
- 새 `KEY_METRIC_KEYS`(6종)가 핵심지표 그리드·추이 지표 선택지를 정한다. 산업 비교는 이 브랜치에서 건드리지 않는다(80 티켓).

## 결측 처리

| 상황 | 처리 |
|---|---|
| 지표 value null | 카드 "미제공", 배지 없음 |
| yoy null / changeRate null | 배지 미표시, 스트립 "–", 표 "미제공" |
| profitability 없음 또는 전부 null | "주요 비율" 블록 미노출 |
| 기본정보 로딩 중 | 핵심지표는 자리만 잡고 조회하지 않음(연도 확정 후 1회 호출) |
| 기본정보 실패 | 연도 없이 조회(서버 기본 최신) |
| 연도 누락(시계열) | 선 끊김·마커 없음·표 "미제공" |

## 구조

```
types/metrics.ts            KEY_METRIC_KEYS · KeyMetric.changeRate · Profitability · KeyMetricsData
utils/formatChangeRate.ts   +1.7% 형식
features/key-metrics/       api(v2 정규화) · useKeyMetrics(year 선택) · KeyMetricCard(배지) · ChangeRateBadge · ProfitabilityRow · KeyMetricsSection
features/financial-trend/   types(changeRate) · api(정규화) · TrendChart(스트립·툴팁) · FinancialTrendSection(6종 선택지)
pages/company-detail/       CompanyGrowthTab · CompanyTabNav(growth 활성) · router
mocks/                      keyMetrics(삼성전자 풀·현대차 결측) · financialTrend(changeRate)
```

## 테스트

- key-metrics/api.test: 6종 필터·yoy 전달·profitability 정규화·빈 응답
- KeyMetricsGrid.test: 6장 고정 순서·미제공·배지 유무
- KeyMetricsSection.test: year 생략 시 파라미터 없음·응답 year 제목·profitability 블록 유무
- TrendChart.test: 증감률 스트립·툴팁·표
- CompanyDetailPage.test: growth 탭 라우팅·dataYear 전달·이중 호출 없음

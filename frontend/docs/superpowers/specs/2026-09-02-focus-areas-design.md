# 집중 분야 화면 설계 — S15P21A504-79

2026-09-02 · 담당: 장수철(Frontend) · 서브태스크 105(투자·M&A·인력 화면), 106(조건부 영역·API)

## 목표

기업이 최근 어디에 돈과 사람을 쓰고 있는지 확인하는 "집중 분야" 탭.

## 범위

- `/companies/:id/focus` 탭 활성화
- **확정 영역** (항상 표시)
  - 투자·M&A 이벤트: `GET /activities?type=` — 설비투자/타법인 출자/M&A/사업 양수도 유형 선택(기본 설비투자), 연도·분야·목적·금액
  - 직원 변화: `GET /segments` — 전사 직원 순증감 + 사업부별 순증감(막대), 매출 미공시 부문 표기
- **조건부 영역** (PoC 통과 데이터가 있을 때만)
  - 사업 방향: `GET /focus` direction — 전략 변화·신규 사업·키워드, **"AI 분석" 배지**
  - 연구개발: `GET /focus` rnd — R&D 비용·전년 대비·매출 대비·분야, **"실제 데이터" 배지**
- AI 분석과 실제 데이터 구분: 모든 섹션에 `SourceBadge`(ai / data + 출처명)

## 한계 (백엔드 협업)

- Jira "대상기업" 항목은 `/activities` 응답에 필드가 없어 표시하지 않는다.
- `/activities` 는 type 파라미터가 필수라 유형별로 조회한다(전체 보기 없음).

## 결측 처리

| 상황 | 처리 |
|---|---|
| activities 빈 배열 | "확인 가능한 {유형} 이벤트가 없습니다" |
| field / purpose / amount null | "분야 미상" / "목적 정보 없음" / "금액 미공시" |
| segments 빈 배열 | "확인 가능한 사업부별 직원현황이 없습니다" |
| employeeTotalChange / employeeChange null | "미제공" (0 아님) |
| segment revenue null | "매출 미공시" |
| focus 404 또는 direction·rnd 모두 없음 | 조건부 영역 통째로 미노출 |
| focus 5xx | 안내 + 다시 시도 (확정 영역과 독립) |
| 모르는 activity type | 무시 |

## 구조

```
features/focus-areas/
  types.ts                 ActivityType(4) · InvestmentActivity · WorkforceChange · CompanyFocus
  api.ts                   toActivities/toWorkforce/toFocus 정규화 · fetch 3종 (mock 분기)
  hooks.ts                 useActivities(type) · useWorkforce · useFocus
  ActivitiesSection.tsx    유형 pill + 이벤트 목록
  WorkforceSection.tsx     전사 순증감 + 부문 막대
  FocusDirectionSection.tsx  조건부 direction/rnd 카드
components/common/SourceBadge.tsx  AI 분석 / 실제 데이터 배지
components/common/PillRadioGroup.tsx  범용 pill 라디오
pages/company-detail/CompanyFocusTab.tsx · CompanyTabNav(focus 활성) · router
mocks/focusAreas.ts        삼성전자 풀 / 현대차 확정만 / NAVER 빈 값
```

## 테스트

- api.test: 정규화(모르는 type 제거·최신순·null 채움·direction/rnd 빈 값 → null)
- FocusSections.test: 유형 전환 재조회·빈 상태·재시도 / 전사·부문 증감·미제공 / AI·실제 데이터 배지·404 미노출·부분 표시·오류
- CompanyDetailPage.test: focus 탭 라우팅, 404 시 조건부 영역 미노출

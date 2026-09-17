# 최근 이슈 화면 설계 — S15P21A504-81

2026-09-02 · 담당: 장수철(Frontend) · 서브태스크 109(뉴스 기본정보·원문 링크), 110(AI 결과 조건부·API)

## 목표

기업과 관련된 최근 뉴스와 이슈를 확인하는 "최근 이슈" 탭.

## 범위

- `/companies/:id/issues` 탭 활성화
- **KPI** (`GET /news/stats?newsDays=7&issueDays=30`): 최근 7일 뉴스 수 · 중요/투자/기술 이슈(30일) + 카테고리별 분포 막대
- **중요 뉴스 TOP** (`GET /news/top?days=30&limit=3`): 순위·제목·카테고리·중요도. 없으면 통째로 숨김
- **뉴스 목록** (`GET /news?days=7&sort=&page=&size=6[&category=]`): 정렬(최신순/중요도순)·카테고리 필터·6건 페이지네이션
  - 기본 필드(제목·설명·게시일·원문 새 탭 링크)는 항상
  - AI 필드(카테고리·관련 사업·중요도)는 null 이면 그 요소만 미표시 → AI 실패에도 기본 뉴스 동작
- 세 API 는 독립: 통계·TOP 이 404/실패여도 목록은 정상. 카테고리 필터 선택지는 통계 분포에서 가져오고, 없으면 "전체"만.
- 통계는 탭이 한 번만 조회해 KPI 섹션과 필터가 공유한다(이중 호출 없음).

## 결측 처리

| 상황 | 처리 |
|---|---|
| 목록 빈 배열 | "수집된 최근 뉴스가 없습니다", 페이지네이션 숨김 |
| description / publishedAt / originalUrl null | 요소 미표시 (링크 없으면 제목만) |
| category / relatedBusiness / importanceScore null | 배지 미표시 |
| stats 404 | KPI 숨김 (필터는 "전체"만) |
| stats 5xx | 안내 + 다시 시도 |
| KPI 개별 값 null | "미제공" |
| top 404 / 빈 배열 | 섹션 숨김 |
| 목록 5xx | 안내 + 다시 시도 |

## 구조

```
features/recent-issues/
  types.ts              NewsItem · NewsPage · NewsStats · TopNewsItem · 상수(size 6, days 7/30)
  api.ts                toNewsPage/toNewsStats/toTopNews 정규화 · fetch 3종 (mock 분기)
  hooks.ts              useNews(query) · useNewsStats · useTopNews
  NewsStatsSection.tsx  state 를 받아 KPI·분포 표시
  TopNewsSection.tsx    TOP 3
  NewsListSection.tsx   정렬·카테고리·페이지 + 목록
utils/formatDate.ts     2025-05-13 → 2025.05.13
components/common/PillRadioGroup.tsx  범용 pill 라디오
pages/company-detail/CompanyIssuesTab.tsx · CompanyTabNav(issues 활성) · router
mocks/recentIssues.ts   삼성전자 풀 / 현대차 AI 없음 / NAVER 뉴스 없음
```

## 테스트

- api.test: 정규화(AI 필드 null·total 폴백·기본값·rank 정렬)
- IssueSections.test: 목록 링크·AI 조건부·정렬/카테고리/페이지 재조회·빈 상태·재시도 / KPI 미제공·분포·404 숨김·재시도 / TOP 표시·빈 배열 숨김
- CompanyDetailPage.test: issues 탭 라우팅, 통계·TOP 없어도 목록 표시

## 목업 반영 개정 (2026-09-02)

- 화면 구성: "최근 기업 이슈" 헤더(+ 데이터 기준: 최신 게시일) → KPI 4장(최근 뉴스 수·중요 이슈 수·투자 이슈·기술 이슈) → [최신 뉴스 목록 | 이슈 분포 도넛 · 중요 뉴스 TOP 3]
- 뉴스 목록은 카테고리 칩(색+글자)·제목(원문 새 탭)·설명·관련 사업·게시일·원문 아이콘. 정렬·카테고리 필터·페이지네이션 대신 **"더 많은 뉴스 보기"로 같은 화면에 다음 페이지를 이어 붙인다**(상세 페이지 없음).
- "핵심 요약"·"모든 중요 뉴스 보기" 는 만들지 않는다. TOP 3 항목도 링크 없음.
- 통계는 탭이 1회 조회해 KPI 와 분포 카드가 공유. 404 는 숨기고 5xx 는 분포 카드에서만 재시도 안내.

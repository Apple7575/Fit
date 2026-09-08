package com.ssafy.companyanalysis.news.dto;

/**
 * 뉴스 KPI 응답.
 *
 * <p>두 기간을 함께 쓴다. 뉴스 수는 {@code newsDays}(기본 7일)를, 이슈 관련 값은
 * {@code issueDays}(기본 30일)를 본다. 명세 초안은 {@code days} 하나였는데 화면이
 * "최근 뉴스 수 7일 기준"과 "중요 이슈 최근 30일"을 나란히 보여주므로 둘로 갈렸다.
 *
 * <p>V16 에서 {@code distribution} 이 빠졌다. 카테고리 컬럼이 ERD 에서 사라져 분포를 만들
 * 근거가 없다. 화면의 이슈 분포 카드도 함께 없어진다.
 *
 * <p>이 응답은 중요도 분석 결과에 기댄다. 분석이 안 돌면 뉴스 수만 채워지고 나머지는
 * null 이다. 그때도 화면은 목록을 그대로 보여주므로 이 API 의 실패가 화면 전체를 막지 않는다.
 */
public record NewsStatsResponse(Kpis kpis) {

    /**
     * 상단 KPI.
     *
     * <p>{@code recentNewsDays} 와 {@code issueDays} 는 요청받은 기간을 그대로 되돌려준다.
     * 화면이 "7일 기준"처럼 기간을 함께 보여주는데, 기본값을 프론트와 서버가 각자 들고 있으면
     * 한쪽만 바뀌었을 때 숫자와 설명이 어긋난다.
     *
     * <p>V16 에서 investmentIssueCount · techIssueCount 가 빠졌다. 카테고리로 세던 값이다.
     */
    public record Kpis(
            Long recentNewsCount,
            int recentNewsDays,
            Long importantIssueCount,
            int issueDays
    ) {
    }
}

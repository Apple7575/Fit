package com.ssafy.companyanalysis.news.dto;

import java.math.BigDecimal;
import java.util.List;

/**
 * 뉴스 KPI와 이슈 분포 응답. 명세의 필드와 이름·순서가 같다.
 *
 * <p>두 기간을 함께 쓴다. KPI 의 뉴스 수는 {@code newsDays}(기본 7일)를, 이슈 관련 값과
 * 분포는 {@code issueDays}(기본 30일)를 본다. 명세 초안은 {@code days} 하나였는데 화면이
 * "최근 뉴스 수 7일 기준"과 "중요 이슈 최근 30일"을 나란히 보여주므로 둘로 갈렸다.
 *
 * <p>이 응답은 전부 AI 분석 결과에 기댄다. 분석이 안 돌면 뉴스 수만 채워지고 나머지는
 * null 이다. 그때도 화면은 목록을 그대로 보여주므로 이 API 의 실패가 화면 전체를 막지 않는다.
 */
public record NewsStatsResponse(Kpis kpis, Distribution distribution) {

    /**
     * 상단 KPI 네 장.
     *
     * <p>{@code recentNewsDays} 와 {@code issueDays} 는 요청받은 기간을 그대로 되돌려준다.
     * 화면이 "7일 기준"처럼 기간을 함께 보여주는데, 기본값을 프론트와 서버가 각자 들고 있으면
     * 한쪽만 바뀌었을 때 숫자와 설명이 어긋난다.
     *
     * <p>{@code investmentIssueCount} 와 {@code techIssueCount} 는 중요 이슈 안에서 센 값이다.
     * 즉 {@code importantIssueCount} 의 부분집합이며 둘을 더해도 그보다 크지 않다. 카테고리
     * 전체 건수는 {@link Distribution#byCategory()} 가 따로 준다.
     */
    public record Kpis(
            Long recentNewsCount,
            int recentNewsDays,
            Long importantIssueCount,
            Long investmentIssueCount,
            Long techIssueCount,
            int issueDays
    ) {
    }

    /**
     * 카테고리별 이슈 분포.
     *
     * <p>{@code total} 은 기간 내 <b>분류에 성공한</b> 뉴스 수다. 그래서 KPI 의 뉴스 수보다
     * 작을 수 있고, {@code byCategory} 의 건수 합과는 같다. 분류하지 못한 뉴스를 "기타"로
     * 묶지 않는다 — 분류 실패와 실제로 그 카테고리인 것은 다른 사실이다.
     */
    public record Distribution(int days, Long total, List<CategoryCount> byCategory) {
    }

    /** 카테고리 한 종. {@code ratio} 는 분류된 뉴스 대비 백분율이라 합이 100 이다. */
    public record CategoryCount(String category, long count, BigDecimal ratio) {
    }
}

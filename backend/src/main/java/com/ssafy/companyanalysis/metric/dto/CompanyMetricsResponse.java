package com.ssafy.companyanalysis.metric.dto;

import java.util.List;

/**
 * 단년 지표 통합 조회 응답.
 *
 * <p>{@code year} 는 요청 연도이며, 요청이 없으면 그 기업의 최신 적재 연도다.
 * 적재된 값이 아예 없으면 null 이고 metrics 는 값이 전부 null 인 골격이 된다.
 *
 * <p>{@code metrics} 는 {@code keys} 를 주지 않으면 기본 6종이고, 주면 요청한 지표만
 * 담긴다. 순서는 어느 쪽이든 카탈로그의 display_order 다.
 *
 * <p>{@code profitability} 는 계산에 쓸 원본이 하나도 없어도 블록을 유지한다. 값 없음을
 * 필드 생략으로 표현하지 않는다는 규칙에 따른 것이다
 * (docs/decisions/0001-missing-data-response.md).
 */
public record CompanyMetricsResponse(
        String corpCode,
        Integer year,
        List<MetricValueResponse> metrics,
        ProfitabilityResponse profitability
) {
}

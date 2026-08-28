package com.ssafy.companyanalysis.metric.dto;

import java.util.List;

/**
 * 단년 지표 통합 조회 응답.
 *
 * <p>{@code year} 는 요청 연도이며, 요청이 없으면 그 기업의 최신 적재 연도다.
 * 적재된 값이 아예 없으면 null 이고 metrics 는 값이 전부 null 인 6건이 된다.
 */
public record CompanyMetricsResponse(
        String corpCode,
        Integer year,
        List<MetricValueResponse> metrics
) {
}

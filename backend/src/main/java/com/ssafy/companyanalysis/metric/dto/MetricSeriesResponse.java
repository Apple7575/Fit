package com.ssafy.companyanalysis.metric.dto;

import java.util.List;

/** 지표 하나의 시계열. points 는 연도 오름차순이다. */
public record MetricSeriesResponse(
        String key,
        String label,
        String unit,
        List<MetricPointResponse> points
) {
}

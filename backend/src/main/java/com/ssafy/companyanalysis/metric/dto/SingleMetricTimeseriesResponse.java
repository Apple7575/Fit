package com.ssafy.companyanalysis.metric.dto;

import java.util.List;

/** 지표 하나만 잘라낸 시계열 응답. 통합 조회의 series 한 건과 같은 값이다. */
public record SingleMetricTimeseriesResponse(
        String corpCode,
        String metric,
        String label,
        String unit,
        MetricRangeResponse range,
        List<MetricPointResponse> points
) {
}

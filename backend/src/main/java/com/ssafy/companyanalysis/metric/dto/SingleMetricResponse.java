package com.ssafy.companyanalysis.metric.dto;

import java.math.BigDecimal;

/** 단년 지표 개별 조회 응답. 통합 조회와 값이 같아야 하며 한 건만 잘라 담는다. */
public record SingleMetricResponse(
        String corpCode,
        String metric,
        String label,
        Integer year,
        BigDecimal value,
        String unit,
        YoyResponse yoy
) {
}

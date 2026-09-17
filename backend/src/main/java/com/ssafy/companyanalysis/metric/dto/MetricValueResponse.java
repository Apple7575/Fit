package com.ssafy.companyanalysis.metric.dto;

import java.math.BigDecimal;

/**
 * 통합 조회 응답의 metrics[] 요소.
 *
 * <p>값이 없으면 {@code value} 는 null 이다. 0 으로 바꾸지 않는다 —
 * "적자 0원"과 "미공시"는 다른 사실이다.
 */
public record MetricValueResponse(
        String key,
        String label,
        BigDecimal value,
        String unit,
        YoyResponse yoy
) {
}

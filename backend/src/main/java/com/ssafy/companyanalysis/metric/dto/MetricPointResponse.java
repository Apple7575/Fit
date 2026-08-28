package com.ssafy.companyanalysis.metric.dto;

import java.math.BigDecimal;

/**
 * 시계열의 한 점.
 *
 * <p>구간 안의 모든 연도가 빠짐없이 들어가고, 값이 없는 해는 {@code value} 가 null 이다.
 * 연도를 통째로 빼면 그래프에서 없는 해와 0 인 해를 구분할 수 없다.
 */
public record MetricPointResponse(int year, BigDecimal value) {
}

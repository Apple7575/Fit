package com.ssafy.companyanalysis.metric.dto;

import java.math.BigDecimal;

/**
 * 시계열의 한 점.
 *
 * <p>구간 안의 모든 연도가 빠짐없이 들어가고, 값이 없는 해는 {@code value} 가 null 이다.
 * 연도를 통째로 빼면 그래프에서 없는 해와 0 인 해를 구분할 수 없다.
 *
 * <p>{@code changeRate} 는 전년 대비 증감률(백분율, 소수 1자리)이다. 구간 첫 해도 비우지
 * 않으려고 조회 구간을 한 해 앞에서 시작한다. 전년 값이 없거나 0 이하면 null 이며,
 * 이는 단년 조회의 yoy 와 같은 규칙이다.
 */
public record MetricPointResponse(int year, BigDecimal value, BigDecimal changeRate) {
}

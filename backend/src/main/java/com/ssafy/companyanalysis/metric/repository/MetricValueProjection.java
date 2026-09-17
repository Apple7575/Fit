package com.ssafy.companyanalysis.metric.repository;

import java.math.BigDecimal;

/**
 * 지표 카탈로그 1행 + 해당 기업·연도의 값 + 전년 값을 한 번에 담는 프로젝션.
 *
 * <p>{@code value}·{@code prevValue} 는 값이 없으면 null 이다. 지표 행 자체는
 * 카탈로그에서 나오므로 값이 없어도 6건은 항상 채워진다.
 */
public interface MetricValueProjection {

    String getMetricCode();

    String getLabel();

    String getUnit();

    short getValueScale();

    BigDecimal getValue();

    BigDecimal getPrevValue();
}

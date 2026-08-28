package com.ssafy.companyanalysis.metric.repository;

import java.math.BigDecimal;

/**
 * 지표 카탈로그 1행 + 그 지표의 연도별 값 1건.
 *
 * <p>값이 있는 연도만 행으로 나온다. 구간 안에 값이 하나도 없는 지표는
 * {@code fiscalYear} 가 null 인 행 하나로 나오며, 빠진 연도를 null 로 채우는 일은
 * 서비스가 한다.
 */
public interface MetricPointProjection {

    String getMetricCode();

    String getLabel();

    String getUnit();

    short getValueScale();

    Integer getFiscalYear();

    BigDecimal getValue();
}

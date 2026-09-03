package com.ssafy.companyanalysis.metric.repository;

import java.math.BigDecimal;

/**
 * 지표 코드와 값만 담는 최소 프로젝션. 수익성·안정성 비율의 원본을 꺼낼 때 쓴다.
 *
 * <p>라벨·단위·자릿수가 없는 것은 이 값들이 응답에 그대로 실리지 않고 비율로 계산된 뒤
 * 버려지기 때문이다.
 */
public interface MetricAmountProjection {

    String getMetricCode();

    BigDecimal getValue();
}

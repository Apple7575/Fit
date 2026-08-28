package com.ssafy.companyanalysis.comparison.repository;

import java.math.BigDecimal;

/**
 * 동일 산업 비교의 네이티브 쿼리 결과 한 행. 기업 × (지표 값) 형태로 풀려 나오며,
 * 서비스가 기업 단위로 피벗한다.
 *
 * <p>해당 연도에 값이 하나도 없는 기업은 {@code metricCode} 가 null 인 행 하나로 나온다.
 * value_scale 은 metric 을 LEFT JOIN 하므로 그 경우 null 이다.
 */
public interface IndustryComparisonProjection {

    String getCorpCode();

    String getCorpName();

    String getMetricCode();

    BigDecimal getValue();

    Short getValueScale();
}

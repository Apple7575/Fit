package com.ssafy.companyanalysis.comparison.repository;

import java.math.BigDecimal;

/**
 * 산업 비교의 네이티브 쿼리 결과 한 행. 기업 × 연도 × 지표 형태로 풀려 나오며,
 * 서비스가 기업 단위로 피벗한다.
 *
 * <p>요청 연도에 값이 하나도 없는 기업은 {@code metricCode} 가 null 인 행 하나로 나온다.
 * value_scale 은 metric 을 LEFT JOIN 하므로 그 경우 null 이다.
 *
 * <p>{@code fiscalYear} 가 있는 이유는 매출 성장률 때문이다. 성장률은 요청 연도와 전년
 * 두 해의 매출이 있어야 계산되므로 한 쿼리로 두 해를 가져오고 서비스가 연도로 가른다.
 */
public interface IndustryComparisonProjection {

    String getCorpCode();

    String getCorpName();

    String getMetricCode();

    Integer getFiscalYear();

    BigDecimal getValue();

    Short getValueScale();
}

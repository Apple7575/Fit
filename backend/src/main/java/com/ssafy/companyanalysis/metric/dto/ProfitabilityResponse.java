package com.ssafy.companyanalysis.metric.dto;

import java.math.BigDecimal;

/**
 * 수익성·안정성 비율. 셋 다 백분율이고 소수 1자리다.
 *
 * <p>{@code operatingMargin} 은 영업이익÷매출, {@code netMargin} 은 당기순이익÷매출,
 * {@code debtRatio} 는 부채총계÷자본총계다.
 *
 * <p>분모가 없거나 0 이하면 그 비율만 null 이고 블록 자체는 유지한다. 매출이 0 인 해의
 * 이익률, 자본잠식 기업의 부채비율은 숫자를 만들 수는 있어도 뜻이 없어서 계산하지 않는다.
 */
public record ProfitabilityResponse(
        BigDecimal operatingMargin,
        BigDecimal netMargin,
        BigDecimal debtRatio
) {
}

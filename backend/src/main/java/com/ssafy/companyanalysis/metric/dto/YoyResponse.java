package com.ssafy.companyanalysis.metric.dto;

import java.math.BigDecimal;

/**
 * 전년 대비.
 *
 * <p>{@code changeRate} 는 전년 값이 0 이하이거나 당년 값이 없으면 null 이다.
 * 적자(음수) 기준의 증가율은 부호가 뒤집혀 오해를 부르므로 계산하지 않는다.
 * 이때도 {@code prevValue} 는 그대로 내보내 FE 가 직접 비교할 수 있게 한다.
 */
public record YoyResponse(BigDecimal prevValue, BigDecimal changeRate) {
}

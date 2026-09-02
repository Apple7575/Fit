package com.ssafy.companyanalysis.comparison.dto;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

/**
 * 동일 산업 비교 응답. 현재 기업을 포함해 같은 산업군 기업들의 지표값을 회사별로 담는다.
 * 값이 없는 지표는 {@code null}(0 변환 금지, F-12).
 *
 * <p>{@code year} 는 적재된 값이 하나도 없는 기업에서 null 이다. 지표 조회의 year 와 규칙이 같다.
 */
public record IndustryComparisonResponse(
        Integer year,
        Industry industry,
        List<String> metrics,
        List<Company> companies
) {

    /** 비교 기준 산업(KSIC 중분류). companyCount 는 비교군에 포함된 기업 수다. */
    public record Industry(String code, String name, int companyCount) {
    }

    /** 기업 한 곳의 비교값. values 의 키는 metrics 와 같은 지표 슬러그다. */
    public record Company(String corpCode, String corpName, boolean isTarget, Map<String, BigDecimal> values) {
    }
}

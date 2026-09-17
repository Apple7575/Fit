package com.ssafy.companyanalysis.comparison.dto;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

/**
 * 동일 산업 비교 응답. 현재 기업과 사용자가 고른 기업(peers)의 지표값을 회사별로 담는다.
 * 값이 없는 지표는 {@code null}(0 변환 금지, F-12).
 *
 * <p>{@code year} 는 적재된 값이 하나도 없는 기업에서 null 이다. 지표 조회의 year 와 규칙이 같다.
 *
 * <p>{@code metrics} 는 v2 에서 4종에서 7종으로 늘었다. 그중 revenue_growth 와
 * operating_margin 은 적재값이 아니라 조회 시점에 계산하는 파생 지표다.
 */
public record IndustryComparisonResponse(
        Integer year,
        Industry industry,
        List<String> metrics,
        List<Company> companies
) {

    /**
     * 비교 기준 산업(KSIC 중분류).
     *
     * <p>{@code companyCount} 는 그 산업에 속한 전체 기업 수다. v1 에서는 비교군에 실린 수와
     * 같았지만 v2 는 고른 peers 만 실으므로 둘이 갈린다 — 화면이 "이 산업에 몇 곳이 있는데
     * 그중 몇 곳을 골랐다"를 보여주려면 산업 전체 수가 필요하다.
     */
    public record Industry(String code, String name, int companyCount) {
    }

    /** 기업 한 곳의 비교값. values 의 키는 metrics 와 같은 지표 슬러그다. */
    public record Company(String corpCode, String corpName, boolean isTarget, Map<String, BigDecimal> values) {
    }
}

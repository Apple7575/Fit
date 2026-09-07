package com.ssafy.companyanalysis.focus.dto;

import java.math.BigDecimal;
import java.util.List;

/**
 * 사업부별 매출·인력 증감 응답. 명세의 필드와 이름·순서가 같다.
 *
 * <p>{@code employeeTotalChange} 는 전사 직원 수의 전년 대비 증감이다. 명세가 "부문 합과
 * 불일치(산식 확정 필요)"로 열어 둔 값이었고, 직원 수 지표의 전년 대비 차이로 정했다.
 * 부문 증감의 합과 다른 것은 오류가 아니다 — 인력을 부문별로 공시하지 않은 몫이 전사
 * 숫자에는 들어 있다. 두 값을 한 화면에 놓을 때 합이 맞지 않는다고 보이면 안 된다.
 *
 * <p>부문 식별자를 {@code name} 으로 내보낸다. 기업 개요({@code /profile})는 같은 값을
 * {@code code} 로 내보낸다. 두 응답의 필드명이 다른 것은 프론트가 그렇게 받고 있기
 * 때문이고, 값과 출처는 같은 컬럼이다. 언젠가 한쪽으로 통일하는 편이 낫다.
 */
public record CompanySegmentsResponse(
        Integer year,
        Integer employeeTotalChange,
        List<Segment> segments
) {

    /**
     * 사업부문 한 곳의 매출·비중·인력 증감.
     *
     * <p>매출을 공시하지 않은 부문은 {@code revenue} 와 {@code revenueShare} 가 null 이고,
     * 인력을 공시하지 않았거나 전년 값이 없으면 {@code employeeChange} 가 null 이다.
     * 부문 자체는 존재하는 사실이므로 목록에서 빼지 않는다.
     */
    public record Segment(String name, BigDecimal revenue, BigDecimal revenueShare,
                          Integer employeeChange) {
    }
}

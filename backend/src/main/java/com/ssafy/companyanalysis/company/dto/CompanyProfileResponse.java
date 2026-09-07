package com.ssafy.companyanalysis.company.dto;

import java.math.BigDecimal;
import java.util.List;

/**
 * 기업 개요 응답. 명세의 필드와 이름·순서가 같다.
 *
 * <p>{@code totalRevenue} 는 {@code segments} 의 매출 단순합이라 지표 조회의
 * {@code revenue} 와 다른 값이다. 명세가 그렇게 정의했다. 부문 매출은 미공시 부문이
 * 빠져 있고 내부거래 상계도 반영되지 않으므로, 재무제표의 매출액과 맞으리라 기대하면
 * 안 된다. 두 값을 한 화면에서 나란히 보여줄 때는 출처를 구분해 표시해야 한다.
 *
 * <p>{@code year} 는 이 개요가 어느 해 사업보고서에서 나왔는지다. 적재된 개요가 하나도
 * 없으면 null 이다. 서버가 임의의 해를 대신 고르지 않는다
 * (docs/decisions/0001-missing-data-response.md 규칙 5).
 *
 * <p>세 목록은 값이 없어도 null 이 아니라 빈 배열이다(같은 문서 규칙 4).
 */
public record CompanyProfileResponse(
        Integer year,
        List<String> businesses,
        List<Segment> segments,
        BigDecimal totalRevenue,
        List<String> products
) {

    /**
     * 사업부문 한 곳의 매출과 비중.
     *
     * <p>{@code code} 는 기업이 사업보고서에 쓰는 부문 표기 그대로다(DS·DX 등).
     * 표준 코드체계가 없어 기업마다 다르다.
     *
     * <p>매출을 공시하지 않은 부문은 {@code revenue} 와 {@code revenueShare} 가 둘 다
     * null 이다. 부문 자체는 존재하는 사실이므로 목록에서 빼지 않는다.
     */
    public record Segment(String code, BigDecimal revenue, BigDecimal revenueShare) {
    }
}

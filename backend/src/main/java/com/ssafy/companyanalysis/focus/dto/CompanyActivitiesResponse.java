package com.ssafy.companyanalysis.focus.dto;

import java.math.BigDecimal;
import java.util.List;

/**
 * 투자·M&A 이벤트 목록 응답. 명세의 필드와 이름·순서가 같다.
 *
 * <p>이벤트가 없으면 빈 배열이다. 투자 공시를 낸 적 없는 기업은 흔하고, 그것은 조회 실패가
 * 아니다(docs/decisions/0001-missing-data-response.md 규칙 1).
 *
 * <p>기준연도를 싣지 않는다. 이 응답은 한 해가 아니라 구간을 보여주고, 어느 해 것인지는
 * 항목마다 {@code year} 로 붙어 있다.
 */
public record CompanyActivitiesResponse(List<Item> items) {

    /**
     * 이벤트 한 건.
     *
     * <p>{@code type} 은 요청한 유형과 같은 값이다. 한 유형만 조회하므로 항목마다 같은 값이
     * 반복되지만, 화면이 네 유형을 한 타임라인에 섞어 놓기 때문에 항목에 남아 있어야 한다.
     *
     * <p>분야·목적·금액은 공시에 없으면 null 이다. 금액이 null 인 것과 0 원인 것은 다른
     * 사실이라 0 으로 채우지 않는다.
     */
    public record Item(Integer year, String type, String field, String purpose, BigDecimal amount) {
    }
}

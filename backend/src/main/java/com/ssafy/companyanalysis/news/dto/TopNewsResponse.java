package com.ssafy.companyanalysis.news.dto;

import java.math.BigDecimal;
import java.util.List;

/**
 * 중요 뉴스 상위 N 건 응답. 명세의 필드와 이름·순서가 같다.
 *
 * <p>중요도가 없는 뉴스는 실리지 않는다. 순위를 매길 근거가 없어서다. 그래서 뉴스가 있어도
 * 이 목록은 빌 수 있다 — AI 분석이 아직 안 돌았을 때가 그렇다.
 */
public record TopNewsResponse(List<Item> items) {

    /**
     * 상위 뉴스 한 건. {@code id} 는 목록 조회의 {@code id} 와 같은 값이다(명세 요구).
     *
     * <p>{@code rank} 는 1부터다. 응답 순서로도 알 수 있지만, 화면이 순위를 숫자로 보여주고
     * 네 유형을 섞어 다시 정렬하는 경우가 있어 항목에 남긴다.
     */
    public record Item(int rank, long id, String title, String category, BigDecimal importanceScore) {
    }
}

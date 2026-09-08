package com.ssafy.companyanalysis.news.dto;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

/**
 * 뉴스 목록 응답. 명세의 필드와 이름·순서가 같다.
 *
 * <p>{@code total} 은 페이지가 아니라 조건에 걸린 전체 건수다. 화면이 페이지 버튼을 그리는 데
 * 쓰므로 목록이 비어도 값은 나가야 한다.
 */
public record CompanyNewsResponse(List<Item> items, long total) {

    /**
     * 뉴스 한 건.
     *
     * <p>기본 필드({@code title}·{@code publishedAt}·{@code originalUrl})와 AI 분석 필드
     * ({@code importanceScore})가 섞여 있다. 분석이 실패한 뉴스도 목록에 나가고 AI 필드만
     * null 이다.
     *
     * <p>{@code publishedAt} 은 서울 기준 날짜다. 저장은 시각까지 하지만 화면이 날짜만
     * 보여주고, 시각을 그대로 내보내면 프론트가 표준시 변환을 다시 해야 한다.
     *
     * <p>V16 에서 description · category · relatedBusiness 가 빠졌다. 근거 컬럼이 ERD 에서
     * 사라졌고, 프론트는 없는 필드를 null 로 접어 해당 자리를 그리지 않는다.
     */
    public record Item(
            long id,
            String title,
            LocalDate publishedAt,
            String originalUrl,
            BigDecimal importanceScore
    ) {
    }
}

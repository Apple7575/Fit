package com.ssafy.companyanalysis.news.repository;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * 뉴스 한 건. 응답 항목과 1:1 이라 파생값이 없다.
 *
 * <p>{@code publishedAt} 이 날짜인 것은 쿼리에서 서울 기준으로 잘라 오기 때문이다. 저장은
 * 시각까지 하지만 응답에는 날짜만 나간다.
 */
public interface NewsItemProjection {

    long getId();

    String getTitle();

    String getDescription();

    LocalDate getPublishedAt();

    String getOriginalUrl();

    /** AI 분류 결과. 분석이 실패했으면 null. */
    String getCategory();

    /** AI 가 뽑은 관련 사업. 없으면 null. */
    String getRelatedBusiness();

    /** AI 중요도 0.0~10.0. 없으면 null 이며 0 과 다른 사실이다. */
    BigDecimal getImportanceScore();
}

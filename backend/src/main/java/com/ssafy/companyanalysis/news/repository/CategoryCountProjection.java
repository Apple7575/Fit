package com.ssafy.companyanalysis.news.repository;

/**
 * 카테고리별 건수. 비율은 여기 없다 — 전체 건수로 나눠야 나오는 파생값이라 서비스가 만든다.
 */
public interface CategoryCountProjection {

    String getCategory();

    long getCount();
}

package com.ssafy.companyanalysis.company.repository;

/**
 * 네이티브 쿼리 결과 매핑용 인터페이스 프로젝션.
 * 네이티브 쿼리는 record 로 바로 매핑되지 않아 이 형태를 쓴다.
 */
public interface CompanySummaryProjection {

    String getCorpCode();

    String getCorpName();

    String getStockCode();

    String getIndustryCode();

    String getIndustryName();
}

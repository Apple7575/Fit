package com.ssafy.companyanalysis.company.repository;

import java.time.LocalDate;

/**
 * 기업 상세 조회의 네이티브 쿼리 결과 매핑용 인터페이스 프로젝션.
 *
 * <p>v2 에서 stockCode 와 market 이 헤더 응답에서 빠졌다. corp_cls 는 컬럼으로 남아 있지만
 * 이 조회는 더 이상 읽지 않는다. 종목코드는 검색 응답에만 나가므로
 * {@link CompanySummaryProjection} 이 따로 싣는다.
 *
 * <p>dataYear 는 company 테이블에 없는 파생값이라 쿼리에서 서브쿼리로 만들어 싣는다.
 */
public interface CompanyDetailProjection {

    String getCorpCode();

    String getCorpName();

    String getIndustryCode();

    String getIndustryName();

    String getCeoNm();

    LocalDate getEstablishedDate();

    String getAddress();

    String getHomepageUrl();

    /**
     * 이 기업의 최신 적재 회계연도. 화면 전체가 같은 해를 보게 하는 기준값이다.
     * 적재된 지표가 하나도 없으면 null 이다.
     */
    Integer getDataYear();
}

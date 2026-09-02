package com.ssafy.companyanalysis.company.repository;

import java.time.LocalDate;

/**
 * 기업 상세 조회의 네이티브 쿼리 결과 매핑용 인터페이스 프로젝션.
 * market 은 corp_cls 에서 파생하므로 원본 corp_cls 를 그대로 받아 서비스에서 변환한다.
 * dataYear 는 company 테이블에 없는 파생값이라 쿼리에서 서브쿼리로 만들어 싣는다.
 */
public interface CompanyDetailProjection {

    String getCorpCode();

    String getCorpName();

    String getStockCode();

    String getIndustryCode();

    String getIndustryName();

    String getCorpCls();

    String getCeoNm();

    LocalDate getEstablishedDate();

    /**
     * 이 기업의 최신 적재 회계연도. 화면 전체가 같은 해를 보게 하는 기준값이다.
     * 적재된 지표가 하나도 없으면 null 이다.
     */
    Integer getDataYear();
}

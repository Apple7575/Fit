package com.ssafy.companyanalysis.company.repository;

import java.time.LocalDate;

/**
 * 기업 상세 조회의 네이티브 쿼리 결과 매핑용 인터페이스 프로젝션.
 * market 은 corp_cls 에서 파생하므로 원본 corp_cls 를 그대로 받아 서비스에서 변환한다.
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
}

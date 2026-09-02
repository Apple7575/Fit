package com.ssafy.companyanalysis.company.dto;

import java.time.LocalDate;

/**
 * 기업 상세 응답. 명세의 기업 기본정보 필드와 이름·순서가 같다.
 * market 은 corp_cls 에서 파생하며 KOSPI·KOSDAQ·KONEX 외에는 null 이다.
 * dataYear 는 이 기업의 최신 적재 연도로, 화면이 기준연도를 스스로 정하지 않게 하려고 싣는다.
 */
public record CompanyDetailResponse(
        String corpCode,
        String corpName,
        String stockCode,
        String industryCode,
        String industryName,
        String market,
        String ceo,
        LocalDate establishedDate,
        Integer dataYear
) {
}

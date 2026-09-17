package com.ssafy.companyanalysis.company.dto;

/** 검색 결과 한 건. 명세의 items[] 요소와 필드명이 같다. */
public record CompanySummaryResponse(
        String corpCode,
        String corpName,
        String stockCode,
        String industryCode,
        String industryName
) {
}

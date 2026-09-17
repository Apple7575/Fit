package com.ssafy.companyanalysis.company.dto;

import java.util.List;

/** 검색 응답 본문. 결과가 없으면 items 는 빈 배열, total 은 0 이다. */
public record CompanySearchResponse(
        List<CompanySummaryResponse> items,
        long total
) {
}

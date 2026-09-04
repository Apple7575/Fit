package com.ssafy.companyanalysis.company.dto;

import java.time.LocalDate;

/**
 * 기업 헤더 응답. 명세의 필드와 이름·순서가 같다.
 *
 * <p>v2 에서 stockCode 와 market 이 빠지고 address·homepageUrl 이 들어왔다. 종목코드와
 * 시장 구분은 헤더 어디에도 표시하지 않아 응답에 실을 이유가 없었다. 종목코드는 검색
 * 결과에 그대로 나간다.
 *
 * <p>dataYear 는 이 기업의 최신 적재 연도다. 상세·지표·산업 비교가 저마다 기준연도를
 * 정하면 한 화면에 다른 해가 섞이므로, 전 화면의 기준연도를 여기 하나로 모은다.
 */
public record CompanyDetailResponse(
        String corpCode,
        String corpName,
        String industryCode,
        String industryName,
        String ceo,
        LocalDate establishedDate,
        String address,
        String homepageUrl,
        Integer dataYear
) {
}

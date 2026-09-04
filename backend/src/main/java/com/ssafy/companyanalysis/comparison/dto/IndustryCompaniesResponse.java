package com.ssafy.companyanalysis.comparison.dto;

import java.util.List;

/**
 * 비교 후보 기업 목록 응답. 산업 비교 화면의 "기업 추가" 드롭다운을 채운다.
 *
 * <p>없는 industryCode 는 오류가 아니다. {@code industry} 가 null 이고 {@code companies} 가
 * 빈 배열인 200 이다. 후보 목록은 화면을 여는 순간 자동으로 불리므로, 산업 정보가 아직
 * 적재되지 않은 기업에서 404 를 내면 비교 화면 전체가 오류로 보인다(결측 응답 기준 1번).
 *
 * <p>기업 항목에 지표값을 싣지 않는 것은 이 응답이 선택 UI 전용이기 때문이다. 값은 기업을
 * 고른 뒤 {@code /api/companies/{corpCode}/industry-comparison} 이 한 번에 가져온다.
 * 여기에 값을 함께 실으면 같은 숫자가 두 응답에서 서로 다른 기준연도로 나갈 수 있다.
 */
public record IndustryCompaniesResponse(Industry industry, List<Company> companies) {

    /** 비교 기준 산업(KSIC 중분류). */
    public record Industry(String code, String name) {
    }

    /** 후보 기업 한 곳. 목록을 그리는 데 필요한 최소 정보만 담는다. */
    public record Company(String corpCode, String corpName) {
    }
}

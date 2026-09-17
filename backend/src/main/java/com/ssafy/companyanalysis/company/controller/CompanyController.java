package com.ssafy.companyanalysis.company.controller;

import com.ssafy.companyanalysis.company.dto.CompanyDetailResponse;
import com.ssafy.companyanalysis.company.dto.CompanyProfileResponse;
import com.ssafy.companyanalysis.company.dto.CompanySearchResponse;
import com.ssafy.companyanalysis.company.service.CompanyDetailService;
import com.ssafy.companyanalysis.company.service.CompanyProfileService;
import com.ssafy.companyanalysis.company.service.CompanySearchService;
import com.ssafy.companyanalysis.global.response.ApiResponse;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/companies")
@Validated
public class CompanyController {

    private static final int DEFAULT_PAGE = 1;
    private static final int DEFAULT_SIZE = 20;

    /** 개요 테이블의 fiscal_year CHECK 제약과 같은 범위. 벗어나면 조회 전에 400 이다. */
    private static final int MIN_YEAR = 1900;
    private static final int MAX_YEAR = 2100;

    private final CompanySearchService companySearchService;
    private final CompanyDetailService companyDetailService;
    private final CompanyProfileService companyProfileService;

    public CompanyController(CompanySearchService companySearchService,
                            CompanyDetailService companyDetailService,
                            CompanyProfileService companyProfileService) {
        this.companySearchService = companySearchService;
        this.companyDetailService = companyDetailService;
        this.companyProfileService = companyProfileService;
    }

    /**
     * 기업명(부분일치) 또는 종목코드로 검색한다.
     *
     * <p>{@code keyword} 가 없거나 공백뿐이면 400 INVALID_PARAMETER 다.
     * 프론트에서도 막지만 서버에서 한 번 더 막는다.
     */
    @GetMapping
    public ApiResponse<CompanySearchResponse> search(
            @RequestParam @NotBlank String keyword,
            @RequestParam(defaultValue = "" + DEFAULT_PAGE) @Min(1) int page,
            @RequestParam(defaultValue = "" + DEFAULT_SIZE) @Min(1) @Max(100) int size) {

        return ApiResponse.ok(companySearchService.search(keyword, page, size));
    }

    /** corpCode 로 기업 기본정보를 조회한다. 없으면 404 COMPANY_NOT_FOUND 다. */
    @GetMapping("/{corpCode}")
    public ApiResponse<CompanyDetailResponse> getCompany(@PathVariable String corpCode) {
        return ApiResponse.ok(companyDetailService.getCompany(corpCode));
    }

    /**
     * 기업 개요(주요 사업·사업부문 매출·주요 제품)를 조회한다. 없는 기업은 404 COMPANY_NOT_FOUND 다.
     *
     * <p>개요가 아직 적재되지 않은 기업도 200 이다. 목록은 빈 배열, year 와 totalRevenue 는
     * null 로 나간다.
     *
     * @param year 생략하면 이 기업의 개요가 적재된 최신 연도
     */
    @GetMapping("/{corpCode}/profile")
    public ApiResponse<CompanyProfileResponse> getProfile(
            @PathVariable String corpCode,
            @RequestParam(required = false) @Min(MIN_YEAR) @Max(MAX_YEAR) Integer year) {

        return ApiResponse.ok(companyProfileService.getProfile(corpCode, year));
    }
}

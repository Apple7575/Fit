package com.ssafy.companyanalysis.comparison.controller;

import com.ssafy.companyanalysis.comparison.dto.IndustryComparisonResponse;
import com.ssafy.companyanalysis.comparison.service.IndustryComparisonService;
import com.ssafy.companyanalysis.global.response.ApiResponse;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 동일 산업 비교(US-04). 같은 KSIC 중분류 기업들의 지표값을 회사별로 반환한다.
 */
@RestController
@RequestMapping("/api/companies/{corpCode}/industry-comparison")
@Validated
public class IndustryComparisonController {

    /** company_metric.fiscal_year 의 CHECK 범위와 같다. 벗어나면 조회 전에 400 이다. */
    private static final int MIN_YEAR = 1900;
    private static final int MAX_YEAR = 2100;

    private final IndustryComparisonService industryComparisonService;

    public IndustryComparisonController(IndustryComparisonService industryComparisonService) {
        this.industryComparisonService = industryComparisonService;
    }

    /**
     * 같은 산업군 기업들의 지정 연도 비교값을 반환한다.
     *
     * @param year 생략하면 2025
     */
    @GetMapping
    public ApiResponse<IndustryComparisonResponse> compare(
            @PathVariable String corpCode,
            @RequestParam(required = false) @Min(MIN_YEAR) @Max(MAX_YEAR) Integer year) {

        return ApiResponse.ok(industryComparisonService.compare(corpCode, year));
    }
}

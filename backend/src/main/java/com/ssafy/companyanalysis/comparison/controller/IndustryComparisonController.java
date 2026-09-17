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

import java.util.List;

/**
 * 동일 산업 비교(US-04). 대상 기업과 사용자가 고른 기업들의 지표값을 회사별로 반환한다.
 *
 * <p>v2 명세에서 "산업 전체 자동 비교"가 "고른 peers(최대 3) 비교"로 바뀌었다.
 * 비교할 기업을 고르는 후보 목록은 {@code GET /api/industries/{industryCode}/companies} 다.
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
     * 대상 기업과 고른 기업들의 지정 연도 비교값을 반환한다.
     *
     * @param peers   쉼표로 구분한 비교 기업 corpCode. 최대 3개, 생략하면 대상 기업만
     * @param metrics 쉼표로 구분한 지표 슬러그. 생략하면 명세의 7종 전부
     * @param year    생략하면 서버가 정한 기준연도. 단년 조회와 달리 기업 하나가 아니라
     *                적재 전체에서 정한다 — 여러 기업을 한 해로 나란히 놓아야 하기 때문이다
     */
    @GetMapping
    public ApiResponse<IndustryComparisonResponse> compare(
            @PathVariable String corpCode,
            @RequestParam(required = false) List<String> peers,
            @RequestParam(required = false) List<String> metrics,
            @RequestParam(required = false) @Min(MIN_YEAR) @Max(MAX_YEAR) Integer year) {

        return ApiResponse.ok(industryComparisonService.compare(corpCode, peers, metrics, year));
    }
}

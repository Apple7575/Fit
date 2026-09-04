package com.ssafy.companyanalysis.comparison.controller;

import com.ssafy.companyanalysis.comparison.dto.IndustryCompaniesResponse;
import com.ssafy.companyanalysis.comparison.service.IndustryCompaniesService;
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
 * 비교 후보 기업 목록. 산업 비교 화면에서 비교할 기업을 고르는 드롭다운을 채운다.
 *
 * <p>경로가 기업이 아니라 산업에서 시작하므로 {@code /api/companies} 밑이 아니라
 * {@code /api/industries} 밑이다. 같은 비교 도메인이라 패키지는 comparison 을 함께 쓴다.
 */
@RestController
@RequestMapping("/api/industries/{industryCode}/companies")
@Validated
public class IndustryCompaniesController {

    /** 명세가 정한 기본값. 드롭다운 하나를 채우는 데 50개면 넉넉하다. */
    private static final int DEFAULT_LIMIT = 50;

    /** 검색 API 의 size 와 같은 상한이다. 목록 조회의 상한을 엔드포인트마다 다르게 둘 이유가 없다. */
    private static final int MAX_LIMIT = 100;

    private final IndustryCompaniesService industryCompaniesService;

    public IndustryCompaniesController(IndustryCompaniesService industryCompaniesService) {
        this.industryCompaniesService = industryCompaniesService;
    }

    /**
     * 같은 KSIC 중분류 기업을 정렬 지표 기준 내림차순으로 반환한다.
     *
     * <p>없는 industryCode 는 404 가 아니라 빈 목록의 200 이다.
     *
     * @param sort  정렬에 쓸 지표 슬러그. 생략하면 revenue. 카탈로그에 없으면 400 INVALID_PARAMETER
     * @param limit 최대 반환 개수. 생략하면 50
     */
    @GetMapping
    public ApiResponse<IndustryCompaniesResponse> listCandidates(
            @PathVariable String industryCode,
            @RequestParam(required = false) String sort,
            @RequestParam(defaultValue = "" + DEFAULT_LIMIT) @Min(1) @Max(MAX_LIMIT) int limit) {

        return ApiResponse.ok(industryCompaniesService.listCandidates(industryCode, sort, limit));
    }
}

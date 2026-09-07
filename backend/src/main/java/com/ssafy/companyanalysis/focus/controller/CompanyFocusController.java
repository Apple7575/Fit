package com.ssafy.companyanalysis.focus.controller;

import com.ssafy.companyanalysis.focus.dto.CompanyFocusResponse;
import com.ssafy.companyanalysis.focus.service.CompanyFocusService;
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
 * 집중 분야 화면의 사업 방향·R&D 조회.
 *
 * <p>응답의 direction 은 AI 분석 결과이고 rnd 는 공시 수치다. 두 블록의 출처가 다르다는 것이
 * 이 API 의 핵심이라 화면도 앞의 것만 "AI 분석"으로 구분해 표시한다.
 */
@RestController
@RequestMapping("/api/companies/{corpCode}/focus")
@Validated
public class CompanyFocusController {

    /** 집중 분야 테이블의 fiscal_year CHECK 제약과 같은 범위. 벗어나면 조회 전에 400 이다. */
    private static final int MIN_YEAR = 1900;
    private static final int MAX_YEAR = 2100;

    private final CompanyFocusService companyFocusService;

    public CompanyFocusController(CompanyFocusService companyFocusService) {
        this.companyFocusService = companyFocusService;
    }

    /**
     * 사업 방향과 R&D 지표를 반환한다. 값이 없어도 두 블록의 키는 유지된다.
     *
     * @param year 생략하면 이 기업의 집중 분야 데이터가 있는 최신 연도
     */
    @GetMapping
    public ApiResponse<CompanyFocusResponse> getFocus(
            @PathVariable String corpCode,
            @RequestParam(required = false) @Min(MIN_YEAR) @Max(MAX_YEAR) Integer year) {

        return ApiResponse.ok(companyFocusService.getFocus(corpCode, year));
    }
}

package com.ssafy.companyanalysis.company.controller;

import com.ssafy.companyanalysis.company.dto.CompanySearchResponse;
import com.ssafy.companyanalysis.company.service.CompanySearchService;
import com.ssafy.companyanalysis.global.response.ApiResponse;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/companies")
@Validated
public class CompanyController {

    private static final int DEFAULT_PAGE = 1;
    private static final int DEFAULT_SIZE = 20;

    private final CompanySearchService companySearchService;

    public CompanyController(CompanySearchService companySearchService) {
        this.companySearchService = companySearchService;
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
}

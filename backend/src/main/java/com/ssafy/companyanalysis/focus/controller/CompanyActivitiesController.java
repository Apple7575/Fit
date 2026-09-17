package com.ssafy.companyanalysis.focus.controller;

import com.ssafy.companyanalysis.focus.dto.CompanyActivitiesResponse;
import com.ssafy.companyanalysis.focus.service.CompanyActivityService;
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

/**
 * 투자·M&A 이벤트 조회.
 *
 * <p>한 번에 한 유형만 준다. 화면은 네 유형을 한 타임라인에 섞어 보여주므로 네 번 호출하고
 * (프론트의 fetchAllActivities), 집중 분야의 설비투자 카드는 type=facility 하나만 부른다.
 * 유형을 여러 개 받게 만들면 두 쓰임 중 어느 쪽도 더 편해지지 않으면서 파라미터 해석만
 * 복잡해진다.
 */
@RestController
@RequestMapping("/api/companies/{corpCode}/activities")
@Validated
public class CompanyActivitiesController {

    /** 이벤트 테이블의 fiscal_year CHECK 제약과 같은 범위. 벗어나면 조회 전에 400 이다. */
    private static final int MIN_YEAR = 1900;
    private static final int MAX_YEAR = 2100;

    private final CompanyActivityService companyActivityService;

    public CompanyActivitiesController(CompanyActivityService companyActivityService) {
        this.companyActivityService = companyActivityService;
    }

    /**
     * 지정 유형의 이벤트를 최신 연도부터 반환한다. 없으면 빈 배열이다.
     *
     * @param type 명세가 정한 네 종 중 하나(facility·corporate_invest·ma·transfer).
     *             모르는 값이면 400 INVALID_PARAMETER 다
     * @param from 시작 회계연도. 생략하면 아래로 제한하지 않는다
     * @param to   끝 회계연도. 생략하면 위로 제한하지 않는다
     */
    @GetMapping
    public ApiResponse<CompanyActivitiesResponse> getActivities(
            @PathVariable String corpCode,
            @RequestParam @NotBlank String type,
            @RequestParam(required = false) @Min(MIN_YEAR) @Max(MAX_YEAR) Integer from,
            @RequestParam(required = false) @Min(MIN_YEAR) @Max(MAX_YEAR) Integer to) {

        return ApiResponse.ok(companyActivityService.getActivities(corpCode, type, from, to));
    }
}

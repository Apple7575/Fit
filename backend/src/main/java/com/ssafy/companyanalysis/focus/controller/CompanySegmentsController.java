package com.ssafy.companyanalysis.focus.controller;

import com.ssafy.companyanalysis.focus.dto.CompanySegmentsResponse;
import com.ssafy.companyanalysis.focus.service.CompanySegmentsService;
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
 * 집중 분야 화면의 사업부별 매출·인력 증감 조회.
 *
 * <p>기업 개요({@code /profile})도 부문 매출을 내보내지만 두 API 는 쓰임이 다르다. 개요는
 * 어느 부문이 얼마를 버는지를 보여주고, 이쪽은 작년과 비교해 무엇이 늘고 줄었는지를
 * 보여준다. 그래서 응답에 증감이 있고 합계는 없다.
 */
@RestController
@RequestMapping("/api/companies/{corpCode}/segments")
@Validated
public class CompanySegmentsController {

    /** 부문 테이블의 fiscal_year CHECK 제약과 같은 범위. 벗어나면 조회 전에 400 이다. */
    private static final int MIN_YEAR = 1900;
    private static final int MAX_YEAR = 2100;

    private final CompanySegmentsService companySegmentsService;

    public CompanySegmentsController(CompanySegmentsService companySegmentsService) {
        this.companySegmentsService = companySegmentsService;
    }

    /**
     * 부문별 매출·비중·인력 증감과 전사 직원 순증감을 반환한다.
     *
     * <p>전사 증감은 부문 증감의 합과 다를 수 있다. 인력을 부문별로 공시하지 않은 몫이
     * 전사 숫자에는 들어 있기 때문이고, 어긋난 것이 아니다.
     *
     * @param year 생략하면 이 기업의 부문·직원 데이터가 있는 최신 연도
     */
    @GetMapping
    public ApiResponse<CompanySegmentsResponse> getSegments(
            @PathVariable String corpCode,
            @RequestParam(required = false) @Min(MIN_YEAR) @Max(MAX_YEAR) Integer year) {

        return ApiResponse.ok(companySegmentsService.getSegments(corpCode, year));
    }
}

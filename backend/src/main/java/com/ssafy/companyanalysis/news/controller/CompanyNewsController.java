package com.ssafy.companyanalysis.news.controller;

import com.ssafy.companyanalysis.global.response.ApiResponse;
import com.ssafy.companyanalysis.news.dto.CompanyNewsResponse;
import com.ssafy.companyanalysis.news.dto.NewsStatsResponse;
import com.ssafy.companyanalysis.news.dto.TopNewsResponse;
import com.ssafy.companyanalysis.news.service.CompanyNewsService;
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
 * 최근 이슈 화면의 뉴스 조회 세 건.
 *
 * <p>한 컨트롤러에 모은 것은 세 응답이 같은 테이블을 다르게 자른 결과여서다. 명세도
 * "/news/top 의 id 는 /news 의 id 와 동일해야 함"이라고 못박아 두었으므로 셋이 함께
 * 움직여야 한다.
 */
@RestController
@RequestMapping("/api/companies/{corpCode}/news")
@Validated
public class CompanyNewsController {

    /** 명세가 정한 기본값. 프론트도 같은 값을 보낸다. */
    private static final int DEFAULT_NEWS_DAYS = 7;
    private static final int DEFAULT_ISSUE_DAYS = 30;
    private static final int DEFAULT_PAGE = 1;
    private static final int DEFAULT_SIZE = 6;
    private static final int DEFAULT_TOP_LIMIT = 3;
    private static final String DEFAULT_SORT = "latest";

    /**
     * 기간 상한. 명세에는 없다.
     *
     * <p>기간을 제한하지 않으면 days 를 크게 넣어 전 기간을 훑는 조회가 되고, 이 테이블은
     * 기업당 행이 계속 늘어나는 쪽이라 인덱스 범위 조건이 사실상 무력해진다. 화면이 쓰는
     * 최대값은 30일이고 두 해치면 어떤 화면에도 넉넉하다.
     */
    private static final int MAX_DAYS = 730;

    /** 목록 페이지 크기 상한. 검색 API 와 같은 값이다. */
    private static final int MAX_SIZE = 100;

    private final CompanyNewsService companyNewsService;

    public CompanyNewsController(CompanyNewsService companyNewsService) {
        this.companyNewsService = companyNewsService;
    }

    /**
     * 최신 뉴스 목록. 없으면 빈 배열이고 total 은 0 이다.
     *
     * <p>V16 에서 category 파라미터가 사라졌다. 자를 근거가 되던 컬럼이 ERD 에서 빠졌다.
     *
     * @param sort latest 또는 importance. 그 밖의 값은 400 INVALID_PARAMETER
     */
    @GetMapping
    public ApiResponse<CompanyNewsResponse> getNews(
            @PathVariable String corpCode,
            @RequestParam(defaultValue = "" + DEFAULT_NEWS_DAYS) @Min(1) @Max(MAX_DAYS) int days,
            @RequestParam(defaultValue = DEFAULT_SORT) @NotBlank String sort,
            @RequestParam(defaultValue = "" + DEFAULT_PAGE) @Min(1) int page,
            @RequestParam(defaultValue = "" + DEFAULT_SIZE) @Min(1) @Max(MAX_SIZE) int size) {

        return ApiResponse.ok(companyNewsService.getNews(corpCode, days, sort, page, size));
    }

    /**
     * 뉴스 KPI.
     *
     * <p>기간이 둘이다. 뉴스 수는 {@code newsDays}, 이슈 관련 값은 {@code issueDays} 를
     * 본다. 명세 초안의 단일 {@code days} 를 화면 구성에 맞춰 나눈 것이다.
     */
    @GetMapping("/stats")
    public ApiResponse<NewsStatsResponse> getStats(
            @PathVariable String corpCode,
            @RequestParam(defaultValue = "" + DEFAULT_NEWS_DAYS) @Min(1) @Max(MAX_DAYS) int newsDays,
            @RequestParam(defaultValue = "" + DEFAULT_ISSUE_DAYS) @Min(1) @Max(MAX_DAYS) int issueDays) {

        return ApiResponse.ok(companyNewsService.getStats(corpCode, newsDays, issueDays));
    }

    /**
     * 중요도 상위 뉴스. 중요도가 매겨진 뉴스가 없으면 빈 배열이다.
     *
     * <p>{@code limit} 상한을 목록 페이지 크기와 같게 둔다. 이 목록은 화면에서 세 건만 쓰지만,
     * 상한이 없으면 기간 전체를 정렬해 끌고 오는 조회가 된다.
     */
    @GetMapping("/top")
    public ApiResponse<TopNewsResponse> getTopNews(
            @PathVariable String corpCode,
            @RequestParam(defaultValue = "" + DEFAULT_ISSUE_DAYS) @Min(1) @Max(MAX_DAYS) int days,
            @RequestParam(defaultValue = "" + DEFAULT_TOP_LIMIT) @Min(1) @Max(MAX_SIZE) int limit) {

        return ApiResponse.ok(companyNewsService.getTopNews(corpCode, days, limit));
    }
}

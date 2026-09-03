package com.ssafy.companyanalysis.metric.controller;

import com.ssafy.companyanalysis.global.response.ApiResponse;
import com.ssafy.companyanalysis.metric.dto.CompanyMetricsResponse;
import com.ssafy.companyanalysis.metric.dto.MetricTimeseriesResponse;
import com.ssafy.companyanalysis.metric.service.CompanyMetricService;
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
 * 핵심지표 단년 조회(F-08)와 시계열 조회(F-14).
 *
 * <p>지표 하나만 보는 개별 조회({@code /{metric}}, {@code /{metric}/timeseries})는
 * v2 명세에서 폐기했다. 같은 결과를 {@code keys} 쿼리파라미터로 얻을 수 있어
 * 경로변수 매핑을 유지할 이유가 없다.
 */
@RestController
@RequestMapping("/api/companies/{corpCode}/metrics")
@Validated
public class CompanyMetricController {

    /** company_metric.fiscal_year 의 CHECK 제약과 같은 범위. 벗어나면 조회 전에 400 이다. */
    private static final int MIN_YEAR = 1900;
    private static final int MAX_YEAR = 2100;

    private final CompanyMetricService companyMetricService;

    public CompanyMetricController(CompanyMetricService companyMetricService) {
        this.companyMetricService = companyMetricService;
    }

    /**
     * 지정 연도의 지표와 수익성·안정성 비율을 한 번에 반환한다. 값이 없는 지표도 자리는 유지된다.
     *
     * @param year 생략하면 그 기업의 최신 적재 연도
     * @param keys 쉼표로 구분한 지표 슬러그. 생략하면 기본 6종
     */
    @GetMapping
    public ApiResponse<CompanyMetricsResponse> getMetrics(
            @PathVariable String corpCode,
            @RequestParam(required = false) @Min(MIN_YEAR) @Max(MAX_YEAR) Integer year,
            @RequestParam(required = false) List<String> keys) {

        return ApiResponse.ok(companyMetricService.getMetrics(corpCode, year, keys));
    }

    /**
     * 구간 내 지표별 시계열을 반환한다(F-14). 값이 없는 해도 연도는 빠지지 않는다.
     *
     * @param keys 쉼표로 구분한 지표 슬러그. 생략하면 기본 6종
     */
    @GetMapping("/timeseries")
    public ApiResponse<MetricTimeseriesResponse> getTimeseries(
            @PathVariable String corpCode,
            @RequestParam(required = false) @Min(MIN_YEAR) @Max(MAX_YEAR) Integer from,
            @RequestParam(required = false) @Min(MIN_YEAR) @Max(MAX_YEAR) Integer to,
            @RequestParam(required = false) List<String> keys) {

        return ApiResponse.ok(companyMetricService.getTimeseries(corpCode, from, to, keys));
    }
}

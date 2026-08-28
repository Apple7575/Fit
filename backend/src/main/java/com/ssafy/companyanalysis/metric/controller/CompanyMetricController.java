package com.ssafy.companyanalysis.metric.controller;

import com.ssafy.companyanalysis.global.response.ApiResponse;
import com.ssafy.companyanalysis.metric.dto.CompanyMetricsResponse;
import com.ssafy.companyanalysis.metric.dto.MetricTimeseriesResponse;
import com.ssafy.companyanalysis.metric.dto.SingleMetricResponse;
import com.ssafy.companyanalysis.metric.dto.SingleMetricTimeseriesResponse;
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
 * <p>{@code /timeseries} 는 {@code /{metric}} 과 같은 자리를 두고 겨루지만,
 * Spring 이 경로변수보다 리터럴 경로를 먼저 매칭하므로 충돌하지 않는다.
 * 산업비교(F-20)도 같은 방식으로 이 아래에 붙는다.
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
     * 지정 연도의 지표 6종을 한 번에 반환한다. 값이 없는 지표도 자리는 유지된다.
     *
     * @param year 생략하면 그 기업의 최신 적재 연도
     * @param yoy  false 면 전년 대비를 계산하지 않는다
     */
    @GetMapping
    public ApiResponse<CompanyMetricsResponse> getMetrics(
            @PathVariable String corpCode,
            @RequestParam(required = false) @Min(MIN_YEAR) @Max(MAX_YEAR) Integer year,
            @RequestParam(defaultValue = "true") boolean yoy) {

        return ApiResponse.ok(companyMetricService.getMetrics(corpCode, year, yoy));
    }

    /** 지표 하나만 반환한다. 통합 조회에서 한 건을 잘라낸 것과 값이 같다. */
    @GetMapping("/{metric}")
    public ApiResponse<SingleMetricResponse> getMetric(
            @PathVariable String corpCode,
            @PathVariable String metric,
            @RequestParam(required = false) @Min(MIN_YEAR) @Max(MAX_YEAR) Integer year,
            @RequestParam(defaultValue = "true") boolean yoy) {

        return ApiResponse.ok(companyMetricService.getMetric(corpCode, metric, year, yoy));
    }

    /**
     * 구간 내 지표별 시계열을 반환한다(F-14). 값이 없는 해도 연도는 빠지지 않는다.
     *
     * @param keys 쉼표로 구분한 지표 슬러그. 생략하면 활성 지표 전체
     */
    @GetMapping("/timeseries")
    public ApiResponse<MetricTimeseriesResponse> getTimeseries(
            @PathVariable String corpCode,
            @RequestParam(required = false) @Min(MIN_YEAR) @Max(MAX_YEAR) Integer from,
            @RequestParam(required = false) @Min(MIN_YEAR) @Max(MAX_YEAR) Integer to,
            @RequestParam(required = false) List<String> keys) {

        return ApiResponse.ok(companyMetricService.getTimeseries(corpCode, from, to, keys));
    }

    /** 지표 하나의 시계열. 통합 시계열에서 series 한 건을 잘라낸 것과 같다. */
    @GetMapping("/{metric}/timeseries")
    public ApiResponse<SingleMetricTimeseriesResponse> getMetricTimeseries(
            @PathVariable String corpCode,
            @PathVariable String metric,
            @RequestParam(required = false) @Min(MIN_YEAR) @Max(MAX_YEAR) Integer from,
            @RequestParam(required = false) @Min(MIN_YEAR) @Max(MAX_YEAR) Integer to) {

        return ApiResponse.ok(companyMetricService.getMetricTimeseries(corpCode, metric, from, to));
    }
}

package com.ssafy.companyanalysis.metric.dto;

import java.util.List;

/**
 * 지표 여러 종의 시계열 통합 응답.
 *
 * <p>series 순서는 요청한 keys 순서가 아니라 카탈로그의 display_order 다.
 * 단년 조회({@code /metrics})와 지표 순서를 맞춰 FE 가 같은 색·같은 자리에 그릴 수 있게 한다.
 */
public record MetricTimeseriesResponse(
        MetricRangeResponse range,
        List<MetricSeriesResponse> series
) {
}

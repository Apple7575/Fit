package com.ssafy.companyanalysis.metric.dto;

/** 시계열 조회 구간. 요청값을 그대로 되돌려 FE 가 축을 그릴 때 기준으로 쓴다. */
public record MetricRangeResponse(int from, int to) {
}

package com.ssafy.companyanalysis.metric.controller;

import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.metric.dto.CompanyMetricsResponse;
import com.ssafy.companyanalysis.metric.dto.MetricPointResponse;
import com.ssafy.companyanalysis.metric.dto.MetricRangeResponse;
import com.ssafy.companyanalysis.metric.dto.MetricSeriesResponse;
import com.ssafy.companyanalysis.metric.dto.MetricTimeseriesResponse;
import com.ssafy.companyanalysis.metric.dto.MetricValueResponse;
import com.ssafy.companyanalysis.metric.dto.SingleMetricResponse;
import com.ssafy.companyanalysis.metric.dto.SingleMetricTimeseriesResponse;
import com.ssafy.companyanalysis.metric.dto.YoyResponse;
import com.ssafy.companyanalysis.metric.service.CompanyMetricService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.math.BigDecimal;
import java.util.List;

import static org.hamcrest.Matchers.nullValue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(CompanyMetricController.class)
class CompanyMetricControllerTest {

    private static final String CORP_CODE = "00164779";

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private CompanyMetricService companyMetricService;

    @Test
    @DisplayName("지표 6종을 명세의 키·단위·전년대비 구조로 반환한다")
    void returnsMetricsInSpecShape() throws Exception {
        given(companyMetricService.getMetrics(eq(CORP_CODE), any(), anyBoolean()))
                .willReturn(new CompanyMetricsResponse(CORP_CODE, 2025, List.of(
                        new MetricValueResponse("revenue", "매출액", new BigDecimal("71000000000000"), "KRW",
                                new YoyResponse(new BigDecimal("66193000000000"), new BigDecimal("7.3"))))));

        mockMvc.perform(get("/api/companies/{corpCode}/metrics", CORP_CODE))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.corpCode").value(CORP_CODE))
                .andExpect(jsonPath("$.data.year").value(2025))
                .andExpect(jsonPath("$.data.metrics[0].key").value("revenue"))
                .andExpect(jsonPath("$.data.metrics[0].label").value("매출액"))
                .andExpect(jsonPath("$.data.metrics[0].value").value(71000000000000L))
                .andExpect(jsonPath("$.data.metrics[0].unit").value("KRW"))
                .andExpect(jsonPath("$.data.metrics[0].yoy.prevValue").value(66193000000000L))
                .andExpect(jsonPath("$.data.metrics[0].yoy.changeRate").value(7.3))
                .andExpect(jsonPath("$.error").doesNotExist());
    }

    @Test
    @DisplayName("값이 없는 지표도 key 는 남고 value 는 null 로 직렬화된다")
    void serializesMissingValueAsNull() throws Exception {
        given(companyMetricService.getMetrics(eq(CORP_CODE), any(), anyBoolean()))
                .willReturn(new CompanyMetricsResponse(CORP_CODE, 2025, List.of(
                        new MetricValueResponse("rd_ratio", "R&D/매출", null, "%", null))));

        mockMvc.perform(get("/api/companies/{corpCode}/metrics", CORP_CODE))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.metrics[0].key").value("rd_ratio"))
                .andExpect(jsonPath("$.data.metrics[0].value").hasJsonPath())
                .andExpect(jsonPath("$.data.metrics[0].value").value(nullValue()))
                .andExpect(jsonPath("$.data.metrics[0].yoy").value(nullValue()));
    }

    @Test
    @DisplayName("없는 기업은 404 COMPANY_NOT_FOUND")
    void unknownCompanyIsNotFound() throws Exception {
        given(companyMetricService.getMetrics(eq("00000000"), any(), anyBoolean()))
                .willThrow(new BusinessException(ErrorCode.COMPANY_NOT_FOUND));

        mockMvc.perform(get("/api/companies/{corpCode}/metrics", "00000000"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.error.code").value("COMPANY_NOT_FOUND"));
    }

    @Test
    @DisplayName("year 가 허용 범위를 벗어나면 400 INVALID_PARAMETER")
    void outOfRangeYearIsBadRequest() throws Exception {
        mockMvc.perform(get("/api/companies/{corpCode}/metrics", CORP_CODE).param("year", "1800"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    @Test
    @DisplayName("year 가 숫자가 아니면 400 INVALID_PARAMETER")
    void nonNumericYearIsBadRequest() throws Exception {
        mockMvc.perform(get("/api/companies/{corpCode}/metrics", CORP_CODE).param("year", "작년"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    @Test
    @DisplayName("개별 지표는 값 한 건을 명세 형태로 반환한다")
    void returnsSingleMetric() throws Exception {
        given(companyMetricService.getMetric(eq(CORP_CODE), eq("revenue"), any(), anyBoolean()))
                .willReturn(new SingleMetricResponse(CORP_CODE, "revenue", "매출액", 2025,
                        new BigDecimal("71000000000000"), "KRW",
                        new YoyResponse(new BigDecimal("66193000000000"), new BigDecimal("7.3"))));

        mockMvc.perform(get("/api/companies/{corpCode}/metrics/{metric}", CORP_CODE, "revenue"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.metric").value("revenue"))
                .andExpect(jsonPath("$.data.label").value("매출액"))
                .andExpect(jsonPath("$.data.year").value(2025))
                .andExpect(jsonPath("$.data.value").value(71000000000000L))
                .andExpect(jsonPath("$.data.unit").value("KRW"))
                .andExpect(jsonPath("$.data.yoy.changeRate").value(7.3));
    }

    @Test
    @DisplayName("지원하지 않는 지표는 400 METRIC_NOT_SUPPORTED")
    void unsupportedMetricIsBadRequest() throws Exception {
        given(companyMetricService.getMetric(eq(CORP_CODE), eq("market_cap"), any(), anyBoolean()))
                .willThrow(new BusinessException(ErrorCode.METRIC_NOT_SUPPORTED));

        mockMvc.perform(get("/api/companies/{corpCode}/metrics/{metric}", CORP_CODE, "market_cap"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.error.code").value("METRIC_NOT_SUPPORTED"));
    }

    @Test
    @DisplayName("timeseries 는 경로변수 매핑에 가로채이지 않고 구간·시계열을 반환한다")
    void returnsTimeseries() throws Exception {
        given(companyMetricService.getTimeseries(eq(CORP_CODE), any(), any(), any()))
                .willReturn(new MetricTimeseriesResponse(new MetricRangeResponse(2021, 2025), List.of(
                        new MetricSeriesResponse("revenue", "매출액", "KRW", List.of(
                                new MetricPointResponse(2021, new BigDecimal("42998000000000")),
                                new MetricPointResponse(2022, null))))));

        mockMvc.perform(get("/api/companies/{corpCode}/metrics/timeseries", CORP_CODE))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.range.from").value(2021))
                .andExpect(jsonPath("$.data.range.to").value(2025))
                .andExpect(jsonPath("$.data.series[0].key").value("revenue"))
                .andExpect(jsonPath("$.data.series[0].unit").value("KRW"))
                .andExpect(jsonPath("$.data.series[0].points[0].year").value(2021))
                .andExpect(jsonPath("$.data.series[0].points[0].value").value(42998000000000L))
                .andExpect(jsonPath("$.data.series[0].points[1].year").value(2022))
                .andExpect(jsonPath("$.data.series[0].points[1].value").value(nullValue()));
    }

    @Test
    @DisplayName("keys 에 오타가 있으면 400 METRIC_NOT_SUPPORTED")
    void unsupportedKeysIsBadRequest() throws Exception {
        given(companyMetricService.getTimeseries(eq(CORP_CODE), any(), any(), any()))
                .willThrow(new BusinessException(ErrorCode.METRIC_NOT_SUPPORTED, "지원하지 않는 지표입니다: market_cap"));

        mockMvc.perform(get("/api/companies/{corpCode}/metrics/timeseries", CORP_CODE)
                        .param("keys", "revenue,market_cap"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("METRIC_NOT_SUPPORTED"));
    }

    @Test
    @DisplayName("from 이 to 보다 크면 400 INVALID_PARAMETER")
    void invertedRangeIsBadRequest() throws Exception {
        given(companyMetricService.getTimeseries(eq(CORP_CODE), any(), any(), any()))
                .willThrow(new BusinessException(ErrorCode.INVALID_PARAMETER, "from 은 to 보다 클 수 없습니다."));

        mockMvc.perform(get("/api/companies/{corpCode}/metrics/timeseries", CORP_CODE)
                        .param("from", "2025").param("to", "2021"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    @Test
    @DisplayName("from 이 허용 범위를 벗어나면 서비스를 타기 전에 400")
    void outOfRangeFromIsBadRequest() throws Exception {
        mockMvc.perform(get("/api/companies/{corpCode}/metrics/timeseries", CORP_CODE).param("from", "1800"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    @Test
    @DisplayName("단일 지표 시계열은 지표 정보와 points 만 반환한다")
    void returnsSingleMetricTimeseries() throws Exception {
        given(companyMetricService.getMetricTimeseries(eq(CORP_CODE), eq("revenue"), any(), any()))
                .willReturn(new SingleMetricTimeseriesResponse(CORP_CODE, "revenue", "매출액", "KRW",
                        new MetricRangeResponse(2021, 2021),
                        List.of(new MetricPointResponse(2021, new BigDecimal("42998000000000")))));

        mockMvc.perform(get("/api/companies/{corpCode}/metrics/{metric}/timeseries", CORP_CODE, "revenue"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.corpCode").value(CORP_CODE))
                .andExpect(jsonPath("$.data.metric").value("revenue"))
                .andExpect(jsonPath("$.data.label").value("매출액"))
                .andExpect(jsonPath("$.data.unit").value("KRW"))
                .andExpect(jsonPath("$.data.range.from").value(2021))
                .andExpect(jsonPath("$.data.points[0].value").value(42998000000000L));
    }
}

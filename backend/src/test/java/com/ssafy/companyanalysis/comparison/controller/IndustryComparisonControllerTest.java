package com.ssafy.companyanalysis.comparison.controller;

import com.ssafy.companyanalysis.comparison.dto.IndustryComparisonResponse;
import com.ssafy.companyanalysis.comparison.service.IndustryComparisonService;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(IndustryComparisonController.class)
@AutoConfigureMockMvc(addFilters = false)
class IndustryComparisonControllerTest {

    /** v2 명세의 비교 지표 7종. */
    private static final List<String> METRICS_V2 = List.of(
            "revenue", "revenue_growth", "operating_profit", "operating_margin",
            "employee_count", "average_salary", "rd_ratio");

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private IndustryComparisonService industryComparisonService;

    @Test
    @DisplayName("산업 비교는 대상 표시와 회사별 값을 표준 응답으로 반환한다")
    void comparisonReturnsStandardEnvelope() throws Exception {
        given(industryComparisonService.compare(eq("00164779"), any(), any(), any()))
                .willReturn(new IndustryComparisonResponse(
                        2025,
                        new IndustryComparisonResponse.Industry("26",
                                "전자 부품, 컴퓨터, 영상, 음향 및 통신장비 제조업", 42),
                        METRICS_V2,
                        List.of(
                                new IndustryComparisonResponse.Company("00164779", "SK하이닉스", true,
                                        values(new BigDecimal("71000000000000"), new BigDecimal("20.0"), null)),
                                new IndustryComparisonResponse.Company("00126380", "삼성전자", false,
                                        values(new BigDecimal("300870000000000"), null,
                                                new BigDecimal("124000"))))));

        mockMvc.perform(get("/api/companies/00164779/industry-comparison").param("peers", "00126380"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.year").value(2025))
                .andExpect(jsonPath("$.data.industry.code").value("26"))
                // 응답에 실린 기업 수(2)가 아니라 산업 전체 기업 수다
                .andExpect(jsonPath("$.data.industry.companyCount").value(42))
                .andExpect(jsonPath("$.data.metrics", hasSize(7)))
                .andExpect(jsonPath("$.data.metrics[0]").value("revenue"))
                .andExpect(jsonPath("$.data.metrics[1]").value("revenue_growth"))
                .andExpect(jsonPath("$.data.metrics[3]").value("operating_margin"))
                .andExpect(jsonPath("$.data.companies[0].isTarget").value(true))
                .andExpect(jsonPath("$.data.companies[0].values.revenue").value(71000000000000L))
                .andExpect(jsonPath("$.data.companies[0].values.revenue_growth").value(20.0))
                .andExpect(jsonPath("$.data.companies[0].values.employee_count").value(nullValue()))
                .andExpect(jsonPath("$.data.companies[1].isTarget").value(false))
                .andExpect(jsonPath("$.error").doesNotExist());
    }

    @Test
    @DisplayName("peers 와 metrics 는 쉼표로 나눠 서비스에 넘어간다")
    void commaSeparatedParamsAreSplit() throws Exception {
        given(industryComparisonService.compare(any(), any(), any(), any()))
                .willReturn(empty());

        mockMvc.perform(get("/api/companies/00164779/industry-comparison")
                        .param("peers", "00126380,00401731")
                        .param("metrics", "revenue,operating_margin"))
                .andExpect(status().isOk());

        then(industryComparisonService).should().compare("00164779",
                List.of("00126380", "00401731"), List.of("revenue", "operating_margin"), null);
    }

    @Test
    @DisplayName("파라미터를 주지 않으면 셋 다 null 로 넘어가고 서비스가 기본값을 정한다")
    void omittedParamsArePassedAsNull() throws Exception {
        given(industryComparisonService.compare(any(), any(), any(), any()))
                .willReturn(empty());

        mockMvc.perform(get("/api/companies/00164779/industry-comparison"))
                .andExpect(status().isOk());

        then(industryComparisonService).should().compare("00164779", null, null, null);
    }

    @Test
    @DisplayName("비교 대상이 없어도 대상 기업만 담아 200 으로 반환한다")
    void emptyPeersIsNotAnError() throws Exception {
        given(industryComparisonService.compare(eq("00164779"), any(), any(), any()))
                .willReturn(new IndustryComparisonResponse(
                        2025,
                        new IndustryComparisonResponse.Industry("26", "전자 부품 제조업", 42),
                        METRICS_V2,
                        List.of(new IndustryComparisonResponse.Company("00164779", "SK하이닉스", true,
                                values(null, null, null)))));

        mockMvc.perform(get("/api/companies/00164779/industry-comparison"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.companies", hasSize(1)))
                .andExpect(jsonPath("$.data.companies[0].values.revenue").value(nullValue()));
    }

    @Test
    @DisplayName("없는 기업은 404 COMPANY_NOT_FOUND")
    void unknownCompanyIsNotFound() throws Exception {
        given(industryComparisonService.compare(eq("00000000"), any(), any(), any()))
                .willThrow(new BusinessException(ErrorCode.COMPANY_NOT_FOUND));

        mockMvc.perform(get("/api/companies/00000000/industry-comparison"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.error.code").value("COMPANY_NOT_FOUND"));
    }

    @Test
    @DisplayName("peers 가 3개를 넘으면 400 INVALID_PARAMETER")
    void tooManyPeersIsBadRequest() throws Exception {
        given(industryComparisonService.compare(any(), any(), any(), any()))
                .willThrow(new BusinessException(ErrorCode.INVALID_PARAMETER, "비교 기업은 최대 3곳입니다."));

        mockMvc.perform(get("/api/companies/00164779/industry-comparison")
                        .param("peers", "1,2,3,4"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    @Test
    @DisplayName("7종 밖의 지표는 400 METRIC_NOT_SUPPORTED")
    void unsupportedMetricIsBadRequest() throws Exception {
        given(industryComparisonService.compare(any(), any(), any(), any()))
                .willThrow(new BusinessException(ErrorCode.METRIC_NOT_SUPPORTED, "지원하지 않는 지표입니다: 없는지표"));

        mockMvc.perform(get("/api/companies/00164779/industry-comparison")
                        .param("metrics", "없는지표"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("METRIC_NOT_SUPPORTED"));
    }

    @Test
    @DisplayName("year 가 범위를 벗어나면 400 INVALID_PARAMETER")
    void invalidYearIsBadRequest() throws Exception {
        mockMvc.perform(get("/api/companies/00164779/industry-comparison").param("year", "1800"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    private static IndustryComparisonResponse empty() {
        return new IndustryComparisonResponse(null,
                new IndustryComparisonResponse.Industry(null, null, 0), METRICS_V2, List.of());
    }

    /** 7종을 순서대로 null 로 깔고 인자로 받은 셋만 채운다. */
    private static Map<String, BigDecimal> values(BigDecimal revenue, BigDecimal revenueGrowth,
                                                  BigDecimal employeeCount) {
        Map<String, BigDecimal> values = new LinkedHashMap<>();
        for (String key : METRICS_V2) {
            values.put(key, null);
        }
        values.put("revenue", revenue);
        values.put("revenue_growth", revenueGrowth);
        values.put("employee_count", employeeCount);
        return values;
    }
}

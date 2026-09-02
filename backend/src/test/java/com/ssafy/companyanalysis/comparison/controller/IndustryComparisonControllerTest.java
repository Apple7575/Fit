package com.ssafy.companyanalysis.comparison.controller;

import com.ssafy.companyanalysis.comparison.dto.IndustryComparisonResponse;
import com.ssafy.companyanalysis.comparison.service.IndustryComparisonService;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.hamcrest.Matchers.nullValue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(IndustryComparisonController.class)
class IndustryComparisonControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private IndustryComparisonService industryComparisonService;

    @Test
    @DisplayName("동일 산업 비교는 대상 표시와 회사별 값을 표준 응답으로 반환한다")
    void comparisonReturnsStandardEnvelope() throws Exception {
        given(industryComparisonService.compare(eq("00164779"), any()))
                .willReturn(new IndustryComparisonResponse(
                        2025,
                        new IndustryComparisonResponse.Industry("26",
                                "전자 부품, 컴퓨터, 영상, 음향 및 통신장비 제조업", 2),
                        List.of("revenue", "operating_profit", "employee_count", "average_salary"),
                        List.of(
                                new IndustryComparisonResponse.Company("00164779", "SK하이닉스", true,
                                        values(new BigDecimal("71000000000000"), null)),
                                new IndustryComparisonResponse.Company("00126380", "삼성전자", false,
                                        values(new BigDecimal("300870000000000"),
                                                new BigDecimal("124000"))))));

        mockMvc.perform(get("/api/companies/00164779/industry-comparison"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.year").value(2025))
                .andExpect(jsonPath("$.data.industry.code").value("26"))
                .andExpect(jsonPath("$.data.industry.companyCount").value(2))
                .andExpect(jsonPath("$.data.metrics[0]").value("revenue"))
                .andExpect(jsonPath("$.data.companies[0].isTarget").value(true))
                .andExpect(jsonPath("$.data.companies[0].values.revenue").value(71000000000000L))
                .andExpect(jsonPath("$.data.companies[0].values.employee_count").value(nullValue()))
                .andExpect(jsonPath("$.data.companies[1].isTarget").value(false))
                .andExpect(jsonPath("$.error").doesNotExist());
    }

    @Test
    @DisplayName("비교 대상이 없어도 대상 기업만 담아 200 으로 반환한다")
    void emptyPeersIsNotAnError() throws Exception {
        given(industryComparisonService.compare(eq("00164779"), any()))
                .willReturn(new IndustryComparisonResponse(
                        2025,
                        new IndustryComparisonResponse.Industry("26", "전자 부품 제조업", 1),
                        List.of("revenue", "operating_profit", "employee_count", "average_salary"),
                        List.of(new IndustryComparisonResponse.Company("00164779", "SK하이닉스", true,
                                values(null, null)))));

        mockMvc.perform(get("/api/companies/00164779/industry-comparison"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.companies.length()").value(1))
                .andExpect(jsonPath("$.data.companies[0].values.revenue").value(nullValue()));
    }

    @Test
    @DisplayName("없는 기업은 404 COMPANY_NOT_FOUND")
    void unknownCompanyIsNotFound() throws Exception {
        given(industryComparisonService.compare(eq("00000000"), any()))
                .willThrow(new BusinessException(ErrorCode.COMPANY_NOT_FOUND));

        mockMvc.perform(get("/api/companies/00000000/industry-comparison"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.error.code").value("COMPANY_NOT_FOUND"));
    }

    @Test
    @DisplayName("year 가 범위를 벗어나면 400 INVALID_PARAMETER")
    void invalidYearIsBadRequest() throws Exception {
        mockMvc.perform(get("/api/companies/00164779/industry-comparison").param("year", "1800"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    private Map<String, BigDecimal> values(BigDecimal revenue, BigDecimal employeeCount) {
        Map<String, BigDecimal> values = new LinkedHashMap<>();
        values.put("revenue", revenue);
        values.put("operating_profit", null);
        values.put("employee_count", employeeCount);
        values.put("average_salary", null);
        return values;
    }
}

package com.ssafy.companyanalysis.focus.controller;

import com.ssafy.companyanalysis.focus.dto.CompanyActivitiesResponse;
import com.ssafy.companyanalysis.focus.service.CompanyActivityService;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.math.BigDecimal;
import java.util.List;

import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(CompanyActivitiesController.class)
class CompanyActivitiesControllerTest {

    private static final String CORP_CODE = "00126380";

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private CompanyActivityService companyActivityService;

    @Test
    @DisplayName("이벤트 목록을 명세의 필드명으로 반환한다")
    void returnsStandardEnvelope() throws Exception {
        given(companyActivityService.getActivities(eq(CORP_CODE), eq("facility"), any(), any()))
                .willReturn(new CompanyActivitiesResponse(List.of(
                        new CompanyActivitiesResponse.Item(2025, "facility", "파운드리",
                                "미국 테일러 공장 생산능력 확대", new BigDecimal("23000000000000")),
                        new CompanyActivitiesResponse.Item(2024, "facility", "HBM", null, null))));

        mockMvc.perform(get("/api/companies/{corpCode}/activities", CORP_CODE)
                        .param("type", "facility"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.items", hasSize(2)))
                .andExpect(jsonPath("$.data.items[0].year").value(2025))
                .andExpect(jsonPath("$.data.items[0].type").value("facility"))
                .andExpect(jsonPath("$.data.items[0].field").value("파운드리"))
                .andExpect(jsonPath("$.data.items[0].purpose").value("미국 테일러 공장 생산능력 확대"))
                .andExpect(jsonPath("$.data.items[0].amount").value(23000000000000L))
                // 목적·금액이 없는 건도 키는 남는다.
                .andExpect(jsonPath("$.data.items[1].purpose").hasJsonPath())
                .andExpect(jsonPath("$.data.items[1].purpose").value(nullValue()))
                .andExpect(jsonPath("$.data.items[1].amount").hasJsonPath())
                .andExpect(jsonPath("$.data.items[1].amount").value(nullValue()))
                // 기준연도는 응답에 없다. 항목마다 year 가 붙는다.
                .andExpect(jsonPath("$.data.year").doesNotExist())
                .andExpect(jsonPath("$.error").doesNotExist());
    }

    @Test
    @DisplayName("이벤트가 없으면 빈 배열이다 (오류 아님)")
    void emptyItemsIsNotAnError() throws Exception {
        given(companyActivityService.getActivities(eq(CORP_CODE), eq("ma"), any(), any()))
                .willReturn(new CompanyActivitiesResponse(List.of()));

        mockMvc.perform(get("/api/companies/{corpCode}/activities", CORP_CODE).param("type", "ma"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.items", hasSize(0)));
    }

    @Test
    @DisplayName("type 이 아예 없으면 400 INVALID_PARAMETER")
    void missingTypeIsBadRequest() throws Exception {
        mockMvc.perform(get("/api/companies/{corpCode}/activities", CORP_CODE))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    @Test
    @DisplayName("모르는 type 은 400 INVALID_PARAMETER")
    void unknownTypeIsBadRequest() throws Exception {
        given(companyActivityService.getActivities(anyString(), eq("buyback"), any(), any()))
                .willThrow(new BusinessException(ErrorCode.INVALID_PARAMETER, "지원하지 않는 이벤트 유형입니다."));

        mockMvc.perform(get("/api/companies/{corpCode}/activities", CORP_CODE).param("type", "buyback"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    @Test
    @DisplayName("from/to 를 그대로 서비스에 넘긴다")
    void rangeIsPassedThrough() throws Exception {
        given(companyActivityService.getActivities(CORP_CODE, "facility", 2021, 2025))
                .willReturn(new CompanyActivitiesResponse(List.of()));

        mockMvc.perform(get("/api/companies/{corpCode}/activities", CORP_CODE)
                        .param("type", "facility")
                        .param("from", "2021")
                        .param("to", "2025"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.items", hasSize(0)));
    }

    @Test
    @DisplayName("없는 기업은 404 COMPANY_NOT_FOUND")
    void unknownCompanyIsNotFound() throws Exception {
        given(companyActivityService.getActivities(eq("00000000"), anyString(), any(), any()))
                .willThrow(new BusinessException(ErrorCode.COMPANY_NOT_FOUND));

        mockMvc.perform(get("/api/companies/{corpCode}/activities", "00000000")
                        .param("type", "facility"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error.code").value("COMPANY_NOT_FOUND"));
    }
}

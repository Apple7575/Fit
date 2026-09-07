package com.ssafy.companyanalysis.focus.controller;

import com.ssafy.companyanalysis.focus.dto.CompanyFocusResponse;
import com.ssafy.companyanalysis.focus.service.CompanyFocusService;
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
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(CompanyFocusController.class)
class CompanyFocusControllerTest {

    private static final String CORP_CODE = "00126380";

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private CompanyFocusService companyFocusService;

    @Test
    @DisplayName("사업 방향과 R&D 를 명세의 필드명으로 반환한다")
    void returnsStandardEnvelope() throws Exception {
        given(companyFocusService.getFocus(eq(CORP_CODE), any()))
                .willReturn(new CompanyFocusResponse(2025,
                        new CompanyFocusResponse.Direction(
                                List.of("파운드리", "로봇"), List.of("온디바이스 AI"), "주력을 옮기고 있다"),
                        new CompanyFocusResponse.Rnd(
                                new BigDecimal("37000000000000"), new BigDecimal("8.8"),
                                new BigDecimal("9.3"), List.of("HBM"))));

        mockMvc.perform(get("/api/companies/{corpCode}/focus", CORP_CODE))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.year").value(2025))
                .andExpect(jsonPath("$.data.direction.newBusiness", hasSize(2)))
                .andExpect(jsonPath("$.data.direction.newBusiness[0]").value("파운드리"))
                .andExpect(jsonPath("$.data.direction.keywords[0]").value("온디바이스 AI"))
                .andExpect(jsonPath("$.data.direction.strategyChange").value("주력을 옮기고 있다"))
                .andExpect(jsonPath("$.data.rnd.expense").value(37000000000000L))
                .andExpect(jsonPath("$.data.rnd.growthRate").value(8.8))
                .andExpect(jsonPath("$.data.rnd.revenueRatio").value(9.3))
                .andExpect(jsonPath("$.data.rnd.fields[0]").value("HBM"))
                .andExpect(jsonPath("$.error").doesNotExist());
    }

    @Test
    @DisplayName("데이터가 없어도 200 이고 두 블록의 키는 남는다")
    void emptyFocusIsNotAnError() throws Exception {
        given(companyFocusService.getFocus(eq(CORP_CODE), any()))
                .willReturn(new CompanyFocusResponse(null,
                        new CompanyFocusResponse.Direction(List.of(), List.of(), null),
                        new CompanyFocusResponse.Rnd(null, null, null, List.of())));

        mockMvc.perform(get("/api/companies/{corpCode}/focus", CORP_CODE))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.year").value(nullValue()))
                .andExpect(jsonPath("$.data.direction").hasJsonPath())
                .andExpect(jsonPath("$.data.direction.newBusiness", hasSize(0)))
                .andExpect(jsonPath("$.data.direction.strategyChange").value(nullValue()))
                .andExpect(jsonPath("$.data.rnd").hasJsonPath())
                .andExpect(jsonPath("$.data.rnd.expense").value(nullValue()))
                .andExpect(jsonPath("$.data.rnd.fields", hasSize(0)));
    }

    @Test
    @DisplayName("year 를 주면 서비스에 그대로 넘긴다")
    void yearIsPassedThrough() throws Exception {
        given(companyFocusService.getFocus(CORP_CODE, 2023))
                .willReturn(new CompanyFocusResponse(2023,
                        new CompanyFocusResponse.Direction(List.of(), List.of(), null),
                        new CompanyFocusResponse.Rnd(null, null, null, List.of())));

        mockMvc.perform(get("/api/companies/{corpCode}/focus", CORP_CODE).param("year", "2023"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.year").value(2023));
    }

    @Test
    @DisplayName("year 가 테이블 제약 범위를 벗어나면 400 INVALID_PARAMETER")
    void yearOutOfRangeIsBadRequest() throws Exception {
        mockMvc.perform(get("/api/companies/{corpCode}/focus", CORP_CODE).param("year", "1800"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    @Test
    @DisplayName("없는 기업은 404 COMPANY_NOT_FOUND")
    void unknownCompanyIsNotFound() throws Exception {
        given(companyFocusService.getFocus(eq("00000000"), any()))
                .willThrow(new BusinessException(ErrorCode.COMPANY_NOT_FOUND));

        mockMvc.perform(get("/api/companies/{corpCode}/focus", "00000000"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error.code").value("COMPANY_NOT_FOUND"));
    }
}

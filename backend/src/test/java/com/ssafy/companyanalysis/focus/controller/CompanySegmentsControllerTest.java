package com.ssafy.companyanalysis.focus.controller;

import com.ssafy.companyanalysis.focus.dto.CompanySegmentsResponse;
import com.ssafy.companyanalysis.focus.service.CompanySegmentsService;
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
import java.util.List;

import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(CompanySegmentsController.class)
@AutoConfigureMockMvc(addFilters = false)
class CompanySegmentsControllerTest {

    private static final String CORP_CODE = "00126380";

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private CompanySegmentsService companySegmentsService;

    @Test
    @DisplayName("부문 이름·매출·비중·인력 증감을 명세의 필드명으로 반환한다")
    void returnsStandardEnvelope() throws Exception {
        given(companySegmentsService.getSegments(eq(CORP_CODE), any()))
                .willReturn(new CompanySegmentsResponse(2025, 1000, List.of(
                        new CompanySegmentsResponse.Segment("DS",
                                new BigDecimal("232000000000000"), new BigDecimal("58.0"), 2000),
                        new CompanySegmentsResponse.Segment("SDC", null, null, null))));

        mockMvc.perform(get("/api/companies/{corpCode}/segments", CORP_CODE))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.year").value(2025))
                .andExpect(jsonPath("$.data.employeeTotalChange").value(1000))
                .andExpect(jsonPath("$.data.segments", hasSize(2)))
                // 기업 개요는 같은 값을 code 로 내보내지만 이 응답은 name 이다.
                .andExpect(jsonPath("$.data.segments[0].name").value("DS"))
                .andExpect(jsonPath("$.data.segments[0].revenue").value(232000000000000L))
                .andExpect(jsonPath("$.data.segments[0].revenueShare").value(58.0))
                .andExpect(jsonPath("$.data.segments[0].employeeChange").value(2000))
                .andExpect(jsonPath("$.data.segments[0].code").doesNotExist())
                .andExpect(jsonPath("$.data.segments[1].revenue").hasJsonPath())
                .andExpect(jsonPath("$.data.segments[1].revenue").value(nullValue()))
                .andExpect(jsonPath("$.data.segments[1].employeeChange").hasJsonPath())
                .andExpect(jsonPath("$.data.segments[1].employeeChange").value(nullValue()))
                .andExpect(jsonPath("$.error").doesNotExist());
    }

    @Test
    @DisplayName("감소는 음수로 그대로 나간다")
    void decreaseIsNegative() throws Exception {
        given(companySegmentsService.getSegments(eq(CORP_CODE), any()))
                .willReturn(new CompanySegmentsResponse(2025, -500, List.of(
                        new CompanySegmentsResponse.Segment("DX", null, null, -1000))));

        mockMvc.perform(get("/api/companies/{corpCode}/segments", CORP_CODE))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.employeeTotalChange").value(-500))
                .andExpect(jsonPath("$.data.segments[0].employeeChange").value(-1000));
    }

    @Test
    @DisplayName("데이터가 없어도 200 이고 목록은 빈 배열이다")
    void emptySegmentsIsNotAnError() throws Exception {
        given(companySegmentsService.getSegments(eq(CORP_CODE), any()))
                .willReturn(new CompanySegmentsResponse(null, null, List.of()));

        mockMvc.perform(get("/api/companies/{corpCode}/segments", CORP_CODE))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.year").value(nullValue()))
                .andExpect(jsonPath("$.data.employeeTotalChange").hasJsonPath())
                .andExpect(jsonPath("$.data.employeeTotalChange").value(nullValue()))
                .andExpect(jsonPath("$.data.segments", hasSize(0)));
    }

    @Test
    @DisplayName("year 가 테이블 제약 범위를 벗어나면 400 INVALID_PARAMETER")
    void yearOutOfRangeIsBadRequest() throws Exception {
        mockMvc.perform(get("/api/companies/{corpCode}/segments", CORP_CODE).param("year", "2200"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    @Test
    @DisplayName("없는 기업은 404 COMPANY_NOT_FOUND")
    void unknownCompanyIsNotFound() throws Exception {
        given(companySegmentsService.getSegments(eq("00000000"), any()))
                .willThrow(new BusinessException(ErrorCode.COMPANY_NOT_FOUND));

        mockMvc.perform(get("/api/companies/{corpCode}/segments", "00000000"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error.code").value("COMPANY_NOT_FOUND"));
    }
}

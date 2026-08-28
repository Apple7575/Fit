package com.ssafy.companyanalysis.company.controller;

import com.ssafy.companyanalysis.company.dto.CompanyDetailResponse;
import com.ssafy.companyanalysis.company.dto.CompanySearchResponse;
import com.ssafy.companyanalysis.company.dto.CompanySummaryResponse;
import com.ssafy.companyanalysis.company.service.CompanyDetailService;
import com.ssafy.companyanalysis.company.service.CompanySearchService;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.time.LocalDate;
import java.util.List;

import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(CompanyController.class)
class CompanyControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private CompanySearchService companySearchService;

    @MockitoBean
    private CompanyDetailService companyDetailService;

    @Test
    @DisplayName("정상 검색은 표준 응답 형식으로 기업 식별자와 기업명을 반환한다")
    void searchReturnsStandardEnvelope() throws Exception {
        given(companySearchService.search(eq("하이닉스"), anyInt(), anyInt()))
                .willReturn(new CompanySearchResponse(
                        List.of(new CompanySummaryResponse("00164779", "SK하이닉스", "000660",
                                "26", "전자 부품, 컴퓨터, 영상, 음향 및 통신장비 제조업")),
                        1));

        mockMvc.perform(get("/api/companies").param("keyword", "하이닉스"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.items[0].corpCode").value("00164779"))
                .andExpect(jsonPath("$.data.items[0].corpName").value("SK하이닉스"))
                .andExpect(jsonPath("$.data.items[0].stockCode").value("000660"))
                .andExpect(jsonPath("$.data.items[0].industryCode").value("26"))
                .andExpect(jsonPath("$.data.total").value(1))
                .andExpect(jsonPath("$.error").doesNotExist());
    }

    @Test
    @DisplayName("결과가 없으면 빈 배열과 total 0 을 반환한다 (오류 아님)")
    void emptyResultIsNotAnError() throws Exception {
        given(companySearchService.search(eq("없는기업"), anyInt(), anyInt()))
                .willReturn(new CompanySearchResponse(List.of(), 0));

        mockMvc.perform(get("/api/companies").param("keyword", "없는기업"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.items").isArray())
                .andExpect(jsonPath("$.data.items").isEmpty())
                .andExpect(jsonPath("$.data.total").value(0));
    }

    @Test
    @DisplayName("keyword 가 아예 없으면 400 INVALID_PARAMETER")
    void missingKeywordIsBadRequest() throws Exception {
        mockMvc.perform(get("/api/companies"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    @Test
    @DisplayName("빈 검색어는 400 INVALID_PARAMETER")
    void blankKeywordIsBadRequest() throws Exception {
        mockMvc.perform(get("/api/companies").param("keyword", ""))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    @Test
    @DisplayName("공백만 있는 검색어도 400 INVALID_PARAMETER")
    void whitespaceOnlyKeywordIsBadRequest() throws Exception {
        mockMvc.perform(get("/api/companies").param("keyword", "   "))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    @Test
    @DisplayName("page 가 1 미만이면 400 INVALID_PARAMETER")
    void invalidPageIsBadRequest() throws Exception {
        mockMvc.perform(get("/api/companies").param("keyword", "삼성").param("page", "0"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    @Test
    @DisplayName("기업 상세는 표준 응답 형식으로 기본정보를 반환한다")
    void companyDetailReturnsStandardEnvelope() throws Exception {
        given(companyDetailService.getCompany("00164779"))
                .willReturn(new CompanyDetailResponse("00164779", "SK하이닉스", "000660",
                        "26", "전자 부품, 컴퓨터, 영상, 음향 및 통신장비 제조업",
                        "KOSPI", "곽노정", LocalDate.of(1949, 10, 15)));

        mockMvc.perform(get("/api/companies/00164779"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.corpCode").value("00164779"))
                .andExpect(jsonPath("$.data.industryCode").value("26"))
                .andExpect(jsonPath("$.data.market").value("KOSPI"))
                .andExpect(jsonPath("$.data.ceo").value("곽노정"))
                .andExpect(jsonPath("$.data.establishedDate").value("1949-10-15"))
                .andExpect(jsonPath("$.error").doesNotExist());
    }

    @Test
    @DisplayName("없는 기업은 404 COMPANY_NOT_FOUND")
    void unknownCompanyIsNotFound() throws Exception {
        given(companyDetailService.getCompany("00000000"))
                .willThrow(new BusinessException(ErrorCode.COMPANY_NOT_FOUND));

        mockMvc.perform(get("/api/companies/00000000"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.error.code").value("COMPANY_NOT_FOUND"));
    }
}

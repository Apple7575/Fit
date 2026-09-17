package com.ssafy.companyanalysis.company.controller;

import com.ssafy.companyanalysis.company.dto.CompanyDetailResponse;
import com.ssafy.companyanalysis.company.dto.CompanyProfileResponse;
import com.ssafy.companyanalysis.company.dto.CompanySearchResponse;
import com.ssafy.companyanalysis.company.dto.CompanySummaryResponse;
import com.ssafy.companyanalysis.company.service.CompanyDetailService;
import com.ssafy.companyanalysis.company.service.CompanyProfileService;
import com.ssafy.companyanalysis.company.service.CompanySearchService;
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
import java.time.LocalDate;
import java.util.List;

import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(CompanyController.class)
@AutoConfigureMockMvc(addFilters = false)
class CompanyControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private CompanySearchService companySearchService;

    @MockitoBean
    private CompanyDetailService companyDetailService;

    @MockitoBean
    private CompanyProfileService companyProfileService;

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
                .willReturn(new CompanyDetailResponse("00164779", "SK하이닉스",
                        "26", "전자 부품, 컴퓨터, 영상, 음향 및 통신장비 제조업",
                        "곽노정", LocalDate.of(1949, 10, 15),
                        "경기도 이천시 부발읍 경충대로 2091", "https://www.skhynix.com", 2025));

        mockMvc.perform(get("/api/companies/00164779"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.corpCode").value("00164779"))
                .andExpect(jsonPath("$.data.industryCode").value("26"))
                .andExpect(jsonPath("$.data.ceo").value("곽노정"))
                .andExpect(jsonPath("$.data.establishedDate").value("1949-10-15"))
                .andExpect(jsonPath("$.data.address").value("경기도 이천시 부발읍 경충대로 2091"))
                .andExpect(jsonPath("$.data.homepageUrl").value("https://www.skhynix.com"))
                .andExpect(jsonPath("$.data.dataYear").value(2025))
                // v2 에서 응답에서 빠진 필드들. 남아 있으면 명세와 어긋난다.
                .andExpect(jsonPath("$.data.stockCode").doesNotExist())
                .andExpect(jsonPath("$.data.market").doesNotExist())
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

    @Test
    @DisplayName("기업 개요는 사업·부문·제품을 명세의 필드명으로 반환한다")
    void companyProfileReturnsStandardEnvelope() throws Exception {
        given(companyProfileService.getProfile(eq("00126380"), any()))
                .willReturn(new CompanyProfileResponse(2025,
                        List.of("반도체", "스마트폰", "가전"),
                        List.of(new CompanyProfileResponse.Segment("DS",
                                        new BigDecimal("232000000000000"), new BigDecimal("58.0")),
                                new CompanyProfileResponse.Segment("SDC", null, null)),
                        new BigDecimal("400000000000000"),
                        List.of("HBM", "DRAM")));

        mockMvc.perform(get("/api/companies/00126380/profile"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.year").value(2025))
                .andExpect(jsonPath("$.data.businesses", hasSize(3)))
                .andExpect(jsonPath("$.data.businesses[0]").value("반도체"))
                .andExpect(jsonPath("$.data.segments[0].code").value("DS"))
                .andExpect(jsonPath("$.data.segments[0].revenue").value(232000000000000L))
                .andExpect(jsonPath("$.data.segments[0].revenueShare").value(58.0))
                // 매출을 공시하지 않은 부문도 목록에 남는다. 키를 빼지 않는다.
                .andExpect(jsonPath("$.data.segments[1].code").value("SDC"))
                .andExpect(jsonPath("$.data.segments[1].revenue").hasJsonPath())
                .andExpect(jsonPath("$.data.segments[1].revenue").value(nullValue()))
                .andExpect(jsonPath("$.data.segments[1].revenueShare").hasJsonPath())
                .andExpect(jsonPath("$.data.segments[1].revenueShare").value(nullValue()))
                .andExpect(jsonPath("$.data.totalRevenue").value(400000000000000L))
                .andExpect(jsonPath("$.data.products[0]").value("HBM"))
                .andExpect(jsonPath("$.error").doesNotExist());
    }

    @Test
    @DisplayName("개요가 아직 적재되지 않은 기업도 200 이고 빈 골격이 나간다")
    void emptyProfileIsNotAnError() throws Exception {
        given(companyProfileService.getProfile(eq("00126380"), any()))
                .willReturn(new CompanyProfileResponse(null, List.of(), List.of(), null, List.of()));

        mockMvc.perform(get("/api/companies/00126380/profile"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.year").hasJsonPath())
                .andExpect(jsonPath("$.data.year").value(nullValue()))
                .andExpect(jsonPath("$.data.businesses", hasSize(0)))
                .andExpect(jsonPath("$.data.segments", hasSize(0)))
                .andExpect(jsonPath("$.data.products", hasSize(0)))
                .andExpect(jsonPath("$.data.totalRevenue").hasJsonPath())
                .andExpect(jsonPath("$.data.totalRevenue").value(nullValue()));
    }

    @Test
    @DisplayName("개요의 year 를 주면 서비스에 그대로 넘긴다")
    void profileYearIsPassedThrough() throws Exception {
        given(companyProfileService.getProfile("00126380", 2023))
                .willReturn(new CompanyProfileResponse(2023, List.of("완성차"), List.of(), null, List.of()));

        mockMvc.perform(get("/api/companies/00126380/profile").param("year", "2023"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.year").value(2023))
                .andExpect(jsonPath("$.data.businesses[0]").value("완성차"));
    }

    @Test
    @DisplayName("개요의 year 가 테이블 제약 범위를 벗어나면 400 INVALID_PARAMETER")
    void profileYearOutOfRangeIsBadRequest() throws Exception {
        mockMvc.perform(get("/api/companies/00126380/profile").param("year", "2200"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    @Test
    @DisplayName("없는 기업의 개요는 404 COMPANY_NOT_FOUND")
    void unknownCompanyProfileIsNotFound() throws Exception {
        given(companyProfileService.getProfile(eq("00000000"), any()))
                .willThrow(new BusinessException(ErrorCode.COMPANY_NOT_FOUND));

        mockMvc.perform(get("/api/companies/00000000/profile"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.error.code").value("COMPANY_NOT_FOUND"));
    }
}

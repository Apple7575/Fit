package com.ssafy.companyanalysis.comparison.controller;

import com.ssafy.companyanalysis.comparison.dto.IndustryCompaniesResponse;
import com.ssafy.companyanalysis.comparison.service.IndustryCompaniesService;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(IndustryCompaniesController.class)
@AutoConfigureMockMvc(addFilters = false)
class IndustryCompaniesControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private IndustryCompaniesService industryCompaniesService;

    @Test
    @DisplayName("비교 후보 목록은 산업과 기업 배열을 표준 응답으로 반환한다")
    void candidatesReturnStandardEnvelope() throws Exception {
        given(industryCompaniesService.listCandidates(eq("26"), any(), eq(50)))
                .willReturn(new IndustryCompaniesResponse(
                        new IndustryCompaniesResponse.Industry("26",
                                "전자 부품, 컴퓨터, 영상, 음향 및 통신장비 제조업"),
                        List.of(new IndustryCompaniesResponse.Company("00126380", "삼성전자"),
                                new IndustryCompaniesResponse.Company("00164779", "SK하이닉스"))));

        mockMvc.perform(get("/api/industries/{industryCode}/companies", "26"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.industry.code").value("26"))
                .andExpect(jsonPath("$.data.industry.name")
                        .value("전자 부품, 컴퓨터, 영상, 음향 및 통신장비 제조업"))
                .andExpect(jsonPath("$.data.companies", hasSize(2)))
                .andExpect(jsonPath("$.data.companies[0].corpCode").value("00126380"))
                .andExpect(jsonPath("$.data.companies[0].corpName").value("삼성전자"))
                .andExpect(jsonPath("$.error").doesNotExist());
    }

    @Test
    @DisplayName("없는 industryCode 는 404 가 아니라 빈 배열의 200 이다")
    void unknownIndustryIsEmptyListNotNotFound() throws Exception {
        given(industryCompaniesService.listCandidates(eq("99"), any(), eq(50)))
                .willReturn(new IndustryCompaniesResponse(null, List.of()));

        mockMvc.perform(get("/api/industries/{industryCode}/companies", "99"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.industry").hasJsonPath())
                .andExpect(jsonPath("$.data.industry").value(nullValue()))
                .andExpect(jsonPath("$.data.companies", hasSize(0)))
                .andExpect(jsonPath("$.error").doesNotExist());
    }

    @Test
    @DisplayName("sort 와 limit 을 주지 않으면 sort 는 null 로, limit 은 50 으로 서비스에 넘어간다")
    void defaultsArePassedToService() throws Exception {
        given(industryCompaniesService.listCandidates(any(), any(), anyInt()))
                .willReturn(new IndustryCompaniesResponse(null, List.of()));

        mockMvc.perform(get("/api/industries/{industryCode}/companies", "26"))
                .andExpect(status().isOk());

        then(industryCompaniesService).should().listCandidates("26", null, 50);
    }

    @Test
    @DisplayName("정렬할 수 없는 지표는 400 INVALID_PARAMETER")
    void unsupportedSortIsBadRequest() throws Exception {
        given(industryCompaniesService.listCandidates(eq("26"), eq("없는지표"), anyInt()))
                .willThrow(new BusinessException(ErrorCode.INVALID_PARAMETER, "정렬할 수 없는 지표입니다: 없는지표"));

        mockMvc.perform(get("/api/industries/{industryCode}/companies", "26").param("sort", "없는지표"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"))
                .andExpect(jsonPath("$.data").doesNotExist());
    }

    @Test
    @DisplayName("limit 이 범위를 벗어나면 400 INVALID_PARAMETER")
    void limitOutOfRangeIsBadRequest() throws Exception {
        mockMvc.perform(get("/api/industries/{industryCode}/companies", "26").param("limit", "0"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));

        mockMvc.perform(get("/api/industries/{industryCode}/companies", "26").param("limit", "101"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }
}

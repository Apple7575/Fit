package com.ssafy.companyanalysis.news.controller;

import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.news.dto.CompanyNewsResponse;
import com.ssafy.companyanalysis.news.dto.NewsStatsResponse;
import com.ssafy.companyanalysis.news.dto.TopNewsResponse;
import com.ssafy.companyanalysis.news.service.CompanyNewsService;
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
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(CompanyNewsController.class)
@AutoConfigureMockMvc(addFilters = false)
class CompanyNewsControllerTest {

    private static final String CORP_CODE = "00126380";

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private CompanyNewsService companyNewsService;

    @Test
    @DisplayName("뉴스 목록을 명세의 필드명으로 반환한다")
    void newsListReturnsStandardEnvelope() throws Exception {
        given(companyNewsService.getNews(eq(CORP_CODE), anyInt(), anyString(), anyInt(), anyInt()))
                .willReturn(new CompanyNewsResponse(List.of(
                        new CompanyNewsResponse.Item(10250, "1분기 영업이익 6.6조 원",
                                LocalDate.of(2025, 5, 20), "https://news.example.com/10250",
                                new BigDecimal("9.6")),
                        new CompanyNewsResponse.Item(10241, "공장 건설",
                                LocalDate.of(2025, 5, 13), null, null)), 48));

        mockMvc.perform(get("/api/companies/{corpCode}/news", CORP_CODE))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.items", hasSize(2)))
                .andExpect(jsonPath("$.data.total").value(48))
                .andExpect(jsonPath("$.data.items[0].id").value(10250))
                .andExpect(jsonPath("$.data.items[0].publishedAt").value("2025-05-20"))
                .andExpect(jsonPath("$.data.items[0].importanceScore").value(9.6))
                // 중요도 분석이 실패한 뉴스도 키는 남는다.
                .andExpect(jsonPath("$.data.items[1].importanceScore").hasJsonPath())
                .andExpect(jsonPath("$.data.items[1].importanceScore").value(nullValue()))
                .andExpect(jsonPath("$.error").doesNotExist());
    }

    @Test
    @DisplayName("V16 이후 목록 응답에 description·category·relatedBusiness 키가 없다")
    void newsListDropsRemovedFields() throws Exception {
        given(companyNewsService.getNews(eq(CORP_CODE), anyInt(), anyString(), anyInt(), anyInt()))
                .willReturn(new CompanyNewsResponse(List.of(
                        new CompanyNewsResponse.Item(10250, "1분기 영업이익 6.6조 원",
                                LocalDate.of(2025, 5, 20), "https://news.example.com/10250",
                                new BigDecimal("9.6"))), 1));

        mockMvc.perform(get("/api/companies/{corpCode}/news", CORP_CODE))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.items[0].description").doesNotExist())
                .andExpect(jsonPath("$.data.items[0].category").doesNotExist())
                .andExpect(jsonPath("$.data.items[0].relatedBusiness").doesNotExist());
    }

    @Test
    @DisplayName("목록 파라미터 기본값은 days 7 · sort latest · page 1 · size 6 이다")
    void newsListDefaults() throws Exception {
        given(companyNewsService.getNews(eq(CORP_CODE), anyInt(), anyString(), anyInt(), anyInt()))
                .willReturn(new CompanyNewsResponse(List.of(), 0));

        mockMvc.perform(get("/api/companies/{corpCode}/news", CORP_CODE))
                .andExpect(status().isOk());

        // 명세와 프론트가 같은 기본값을 쓴다.
        org.mockito.Mockito.verify(companyNewsService).getNews(CORP_CODE, 7, "latest", 1, 6);
    }

    @Test
    @DisplayName("정렬·페이지를 그대로 서비스에 넘긴다")
    void newsListPassesQueryThrough() throws Exception {
        given(companyNewsService.getNews(CORP_CODE, 7, "importance", 2, 6))
                .willReturn(new CompanyNewsResponse(List.of(), 0));

        mockMvc.perform(get("/api/companies/{corpCode}/news", CORP_CODE)
                        .param("sort", "importance")
                        .param("page", "2"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.total").value(0));
    }

    @Test
    @DisplayName("category 를 보내도 조회 조건이 되지 않는다 (V16 에서 사라진 파라미터)")
    void categoryParamIsIgnored() throws Exception {
        given(companyNewsService.getNews(eq(CORP_CODE), anyInt(), anyString(), anyInt(), anyInt()))
                .willReturn(new CompanyNewsResponse(List.of(), 0));

        mockMvc.perform(get("/api/companies/{corpCode}/news", CORP_CODE).param("category", "투자"))
                .andExpect(status().isOk());

        // 모르는 파라미터는 400 이 아니라 무시다. 프론트가 아직 붙여 보내도 목록은 나가야 한다.
        org.mockito.Mockito.verify(companyNewsService).getNews(CORP_CODE, 7, "latest", 1, 6);
    }

    @Test
    @DisplayName("page 가 1 미만이면 400 INVALID_PARAMETER")
    void invalidPageIsBadRequest() throws Exception {
        mockMvc.perform(get("/api/companies/{corpCode}/news", CORP_CODE).param("page", "0"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    @Test
    @DisplayName("days 가 상한을 넘으면 400 INVALID_PARAMETER")
    void tooLongPeriodIsBadRequest() throws Exception {
        mockMvc.perform(get("/api/companies/{corpCode}/news", CORP_CODE).param("days", "5000"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    @Test
    @DisplayName("모르는 sort 는 400 INVALID_PARAMETER")
    void unknownSortIsBadRequest() throws Exception {
        given(companyNewsService.getNews(anyString(), anyInt(), eq("popular"), anyInt(), anyInt()))
                .willThrow(new BusinessException(ErrorCode.INVALID_PARAMETER, "지원하지 않는 정렬 기준입니다."));

        mockMvc.perform(get("/api/companies/{corpCode}/news", CORP_CODE).param("sort", "popular"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    @Test
    @DisplayName("KPI 를 명세의 필드명으로 반환한다")
    void statsReturnStandardEnvelope() throws Exception {
        given(companyNewsService.getStats(eq(CORP_CODE), anyInt(), anyInt()))
                .willReturn(new NewsStatsResponse(new NewsStatsResponse.Kpis(48L, 7, 12L, 30)));

        mockMvc.perform(get("/api/companies/{corpCode}/news/stats", CORP_CODE))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.kpis.recentNewsCount").value(48))
                .andExpect(jsonPath("$.data.kpis.recentNewsDays").value(7))
                .andExpect(jsonPath("$.data.kpis.importantIssueCount").value(12))
                .andExpect(jsonPath("$.data.kpis.issueDays").value(30))
                // V16 에서 카테고리 축이 사라졌다. 분포와 투자·기술 KPI 는 응답에 없다.
                .andExpect(jsonPath("$.data.kpis.investmentIssueCount").doesNotExist())
                .andExpect(jsonPath("$.data.kpis.techIssueCount").doesNotExist())
                .andExpect(jsonPath("$.data.distribution").doesNotExist());
    }

    @Test
    @DisplayName("KPI 기본 기간은 newsDays 7 · issueDays 30 이다")
    void statsDefaults() throws Exception {
        given(companyNewsService.getStats(eq(CORP_CODE), anyInt(), anyInt()))
                .willReturn(new NewsStatsResponse(new NewsStatsResponse.Kpis(null, 7, null, 30)));

        mockMvc.perform(get("/api/companies/{corpCode}/news/stats", CORP_CODE))
                .andExpect(status().isOk());

        org.mockito.Mockito.verify(companyNewsService).getStats(CORP_CODE, 7, 30);
    }

    @Test
    @DisplayName("분석이 안 돌아도 200 이고 KPI 키는 남는다")
    void unanalyzedStatsKeepKeys() throws Exception {
        given(companyNewsService.getStats(eq(CORP_CODE), anyInt(), anyInt()))
                .willReturn(new NewsStatsResponse(new NewsStatsResponse.Kpis(48L, 7, null, 30)));

        mockMvc.perform(get("/api/companies/{corpCode}/news/stats", CORP_CODE))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.kpis.recentNewsCount").value(48))
                .andExpect(jsonPath("$.data.kpis.importantIssueCount").hasJsonPath())
                .andExpect(jsonPath("$.data.kpis.importantIssueCount").value(nullValue()));
    }

    @Test
    @DisplayName("상위 뉴스를 순위와 함께 반환한다")
    void topNewsReturnsRanks() throws Exception {
        given(companyNewsService.getTopNews(eq(CORP_CODE), anyInt(), anyInt()))
                .willReturn(new TopNewsResponse(List.of(
                        new TopNewsResponse.Item(1, 10250, "실적 발표", new BigDecimal("9.6")),
                        new TopNewsResponse.Item(2, 10241, "공장 건설", new BigDecimal("9.2")))));

        mockMvc.perform(get("/api/companies/{corpCode}/news/top", CORP_CODE))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.items", hasSize(2)))
                .andExpect(jsonPath("$.data.items[0].rank").value(1))
                .andExpect(jsonPath("$.data.items[0].id").value(10250))
                .andExpect(jsonPath("$.data.items[0].importanceScore").value(9.6))
                .andExpect(jsonPath("$.data.items[0].category").doesNotExist());
    }

    @Test
    @DisplayName("상위 뉴스 기본값은 days 30 · limit 3 이다")
    void topNewsDefaults() throws Exception {
        given(companyNewsService.getTopNews(eq(CORP_CODE), anyInt(), anyInt()))
                .willReturn(new TopNewsResponse(List.of()));

        mockMvc.perform(get("/api/companies/{corpCode}/news/top", CORP_CODE))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.items", hasSize(0)));

        org.mockito.Mockito.verify(companyNewsService).getTopNews(CORP_CODE, 30, 3);
    }

    @Test
    @DisplayName("없는 기업은 세 경로 모두 404 COMPANY_NOT_FOUND")
    void unknownCompanyIsNotFound() throws Exception {
        given(companyNewsService.getNews(eq("00000000"), anyInt(), anyString(), anyInt(), anyInt()))
                .willThrow(new BusinessException(ErrorCode.COMPANY_NOT_FOUND));
        given(companyNewsService.getStats(eq("00000000"), anyInt(), anyInt()))
                .willThrow(new BusinessException(ErrorCode.COMPANY_NOT_FOUND));
        given(companyNewsService.getTopNews(eq("00000000"), anyInt(), anyInt()))
                .willThrow(new BusinessException(ErrorCode.COMPANY_NOT_FOUND));

        for (String path : List.of("/api/companies/00000000/news",
                "/api/companies/00000000/news/stats",
                "/api/companies/00000000/news/top")) {
            mockMvc.perform(get(path))
                    .andExpect(status().isNotFound())
                    .andExpect(jsonPath("$.error.code").value("COMPANY_NOT_FOUND"));
        }
    }
}

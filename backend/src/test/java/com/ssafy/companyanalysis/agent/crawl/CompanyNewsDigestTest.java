package com.ssafy.companyanalysis.agent.crawl;

import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.news.dto.CompanyNewsResponse;
import com.ssafy.companyanalysis.news.service.CompanyNewsService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.mockito.Mockito;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;

class CompanyNewsDigestTest {

    private CompanyNewsService newsService;
    private CompanyNewsDigest digest;

    @BeforeEach
    void setUp() {
        newsService = Mockito.mock(CompanyNewsService.class);
        digest = new CompanyNewsDigest(newsService);
    }

    private static CompanyNewsResponse response(String... titles) {
        List<CompanyNewsResponse.Item> items = java.util.Arrays.stream(titles)
                .map(title -> new CompanyNewsResponse.Item(
                        1L, title, LocalDate.of(2026, 9, 1), "https://news/1", null))
                .toList();
        return new CompanyNewsResponse(items, items.size());
    }

    @Test
    @DisplayName("회사별로 기사 제목을 모아 준다")
    void collectsTitlesPerCompany() {
        given(newsService.getNews(eq("00126380"), anyInt(), any(), anyInt(), anyInt()))
                .willReturn(response("삼성전자 신규 공장 착공"));
        given(newsService.getNews(eq("01384787"), anyInt(), any(), anyInt(), anyInt()))
                .willReturn(response("시프트업 신작 발표"));

        String text = digest.digest(Map.of("corpCodes", List.of("00126380", "01384787")));

        assertThat(text).contains("삼성전자 신규 공장 착공");
        assertThat(text).contains("시프트업 신작 발표");
        assertThat(text).contains("2026-09-01");
    }

    @Test
    @DisplayName("months 를 주면 그만큼 거슬러 올라간다. 없으면 6개월이다")
    void monthsBecomeDays() {
        given(newsService.getNews(any(), anyInt(), any(), anyInt(), anyInt()))
                .willReturn(response("기사"));
        ArgumentCaptor<Integer> days = ArgumentCaptor.forClass(Integer.class);

        digest.digest(Map.of("corpCodes", List.of("00126380")));
        digest.digest(Map.of("corpCodes", List.of("00126380"), "months", 3));

        Mockito.verify(newsService, Mockito.atLeast(2))
                .getNews(any(), days.capture(), any(), anyInt(), anyInt());
        assertThat(days.getAllValues()).containsExactly(180, 90);
    }

    @Test
    @DisplayName("수집된 기사가 하나도 없으면 그렇게 알린다 — 지어내게 두지 않는다")
    void emptyNewsIsReportedNotFaked() {
        given(newsService.getNews(any(), anyInt(), any(), anyInt(), anyInt()))
                .willReturn(new CompanyNewsResponse(List.of(), 0));

        assertThatThrownBy(() -> digest.digest(Map.of("corpCodes", List.of("00126380"))))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.AGENT_SOURCE_UNAVAILABLE);
    }

    @Test
    @DisplayName("기업을 고르지 않았으면 조회하지 않는다")
    void noCompanyMeansNoLookup() {
        assertThatThrownBy(() -> digest.digest(Map.of()))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.AGENT_SOURCE_UNAVAILABLE);

        Mockito.verifyNoInteractions(newsService);
    }
}

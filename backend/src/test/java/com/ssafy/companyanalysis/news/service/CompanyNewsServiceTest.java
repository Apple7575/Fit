package com.ssafy.companyanalysis.news.service;

import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.news.dto.CompanyNewsResponse;
import com.ssafy.companyanalysis.news.dto.NewsStatsResponse;
import com.ssafy.companyanalysis.news.dto.TopNewsResponse;
import com.ssafy.companyanalysis.news.repository.CompanyNewsRepository;
import com.ssafy.companyanalysis.news.repository.NewsItemProjection;
import com.ssafy.companyanalysis.news.repository.NewsKpiProjection;
import com.ssafy.companyanalysis.news.repository.TopNewsProjection;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

/**
 * 기간 계산과 KPI 파생값을 검증한다.
 *
 * <p>뉴스 수집과 AI 분석이 아직 PoC 단계라 값은 없지만, "분석이 안 돌았다"와 "그런 일이
 * 없었다"를 가르는 규칙은 값이 들어오기 전에 고정해 두어야 한다. 나중에 값만 채워졌을 때
 * 화면 표시가 달라지지 않게 하려는 것이다.
 *
 * <p>V16 에서 카테고리 축이 사라져 분포와 투자·기술 KPI 검증이 함께 없어졌다. 남은 분류
 * 축은 중요도 하나다.
 */
class CompanyNewsServiceTest {

    private static final String CORP_CODE = "00126380";

    /** 2026-09-04 12:00 KST 로 시계를 못박는다. 기간 경계를 눈으로 계산할 수 있게. */
    private static final Clock FIXED_CLOCK =
            Clock.fixed(Instant.parse("2026-09-04T03:00:00Z"), ZoneId.of("Asia/Seoul"));

    private CompanyRepository companyRepository;
    private CompanyNewsRepository newsRepository;
    private CompanyNewsService service;

    @BeforeEach
    void setUp() {
        companyRepository = mock(CompanyRepository.class);
        newsRepository = mock(CompanyNewsRepository.class);
        service = new CompanyNewsService(companyRepository, newsRepository, FIXED_CLOCK);

        given(companyRepository.existsById(CORP_CODE)).willReturn(true);
    }

    @Test
    @DisplayName("목록은 기본 필드와 중요도를 그대로 옮기고 total 을 함께 싣는다")
    void mapsNewsItemsAndTotal() {
        List<NewsItemProjection> rows = List.of(
                news(10250, "1분기 영업이익 6.6조 원", "2025-05-20", "9.6"),
                news(10241, "텍사스 파운드리 공장 건설", "2025-05-13", null));
        Page<NewsItemProjection> page = new PageImpl<>(rows, PageRequest.of(0, 6), 48);
        given(newsRepository.findNews(eq(CORP_CODE), any(), anyBoolean(), any())).willReturn(page);

        CompanyNewsResponse response = service.getNews(CORP_CODE, 7, "latest", 1, 6);

        assertThat(response.total()).isEqualTo(48);
        assertThat(response.items()).hasSize(2);
        assertThat(response.items().get(0).id()).isEqualTo(10250);
        assertThat(response.items().get(0).publishedAt()).isEqualTo(LocalDate.of(2025, 5, 20));
        assertThat(response.items().get(0).importanceScore()).isEqualByComparingTo("9.6");
        // 중요도 분석이 실패한 뉴스도 목록에 남고 그 필드만 null 이다.
        assertThat(response.items().get(1).title()).isEqualTo("텍사스 파운드리 공장 건설");
        assertThat(response.items().get(1).importanceScore()).isNull();
    }

    @Test
    @DisplayName("정렬값에 따라 중요도 우선 여부를 조회에 넘긴다")
    void passesSortFlagToQuery() {
        given(newsRepository.findNews(anyString(), any(), anyBoolean(), any())).willReturn(Page.empty());

        service.getNews(CORP_CODE, 7, "importance", 1, 6);
        verify(newsRepository).findNews(eq(CORP_CODE), any(), eq(true), any());

        service.getNews(CORP_CODE, 7, "latest", 1, 6);
        verify(newsRepository).findNews(eq(CORP_CODE), any(), eq(false), any());
    }

    @Test
    @DisplayName("기간은 주입한 시계에서 계산한다 (7일 전)")
    void computesSinceFromClock() {
        given(newsRepository.findNews(anyString(), any(), anyBoolean(), any())).willReturn(Page.empty());

        service.getNews(CORP_CODE, 7, "latest", 1, 6);

        OffsetDateTime expected = OffsetDateTime.now(FIXED_CLOCK).minusDays(7);
        verify(newsRepository).findNews(eq(CORP_CODE), eq(expected), anyBoolean(), any());
    }

    @Test
    @DisplayName("모르는 정렬값은 조용히 최신순으로 넘기지 않고 400 이다")
    void unknownSortIsBadRequest() {
        assertThatThrownBy(() -> service.getNews(CORP_CODE, 7, "popular", 1, 6))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.INVALID_PARAMETER);

        verify(newsRepository, never()).findNews(anyString(), any(), anyBoolean(), any());
    }

    @Test
    @DisplayName("뉴스가 없으면 오류가 아니라 빈 배열과 total 0 이다")
    void emptyNewsIsNotAnError() {
        given(newsRepository.findNews(anyString(), any(), anyBoolean(), any())).willReturn(Page.empty());

        CompanyNewsResponse response = service.getNews(CORP_CODE, 7, "latest", 1, 6);

        assertThat(response.items()).isEmpty();
        assertThat(response.total()).isZero();
    }

    @Test
    @DisplayName("상위 뉴스는 조회 순서대로 1 부터 순위를 매긴다")
    void ranksTopNewsFromOne() {
        List<TopNewsProjection> rows = List.of(
                top(10250, "실적 발표", "9.6"),
                top(10241, "공장 건설", "9.2"),
                top(10238, "HBM4 공급", "8.8"));
        given(newsRepository.findTopNews(eq(CORP_CODE), any(), eq(3))).willReturn(rows);

        TopNewsResponse response = service.getTopNews(CORP_CODE, 30, 3);

        assertThat(response.items()).extracting(TopNewsResponse.Item::rank).containsExactly(1, 2, 3);
        assertThat(response.items().get(0).id()).isEqualTo(10250);
        assertThat(response.items().get(2).importanceScore()).isEqualByComparingTo("8.8");
    }

    @Test
    @DisplayName("중요도가 매겨진 뉴스가 없으면 상위 목록은 빈 배열이다")
    void emptyTopNewsWhenNothingScored() {
        given(newsRepository.findTopNews(anyString(), any(), anyInt())).willReturn(List.of());

        assertThat(service.getTopNews(CORP_CODE, 30, 3).items()).isEmpty();
    }

    @Test
    @DisplayName("KPI 는 두 기간을 각각 쓰고 요청한 기간을 되돌려준다")
    void statsUseTwoPeriodsAndEchoThem() {
        NewsKpiProjection kpi = kpi(12, true);
        given(newsRepository.findKpis(eq(CORP_CODE), any(), any())).willReturn(kpi);
        given(newsRepository.countNews(eq(CORP_CODE), any())).willReturn(48L);

        NewsStatsResponse response = service.getStats(CORP_CODE, 7, 30);

        assertThat(response.kpis().recentNewsCount()).isEqualTo(48);
        assertThat(response.kpis().recentNewsDays()).isEqualTo(7);
        assertThat(response.kpis().importantIssueCount()).isEqualTo(12);
        assertThat(response.kpis().issueDays()).isEqualTo(30);
        // 뉴스 수는 newsDays, 이슈는 issueDays 로 각각 조회한다.
        verify(newsRepository).countNews(CORP_CODE, OffsetDateTime.now(FIXED_CLOCK).minusDays(7));
        verify(newsRepository).findKpis(eq(CORP_CODE),
                eq(OffsetDateTime.now(FIXED_CLOCK).minusDays(30)), any());
    }

    @Test
    @DisplayName("AI 분석이 안 돌았으면 중요 이슈 수는 0 이 아니라 null 이다")
    void unscoredIssueKpisAreNullNotZero() {
        NewsKpiProjection kpi = kpi(0, false);
        given(newsRepository.findKpis(eq(CORP_CODE), any(), any())).willReturn(kpi);
        given(newsRepository.countNews(eq(CORP_CODE), any())).willReturn(48L);

        NewsStatsResponse.Kpis kpis = service.getStats(CORP_CODE, 7, 30).kpis();

        // 뉴스는 수집됐으니 뉴스 수는 나간다. 중요도 기반 값만 미제공이다.
        assertThat(kpis.recentNewsCount()).isEqualTo(48);
        assertThat(kpis.importantIssueCount()).isNull();
    }

    @Test
    @DisplayName("분석은 돌았는데 중요 이슈가 없으면 null 이 아니라 0 이다")
    void scoredButNoImportantIssueIsZero() {
        NewsKpiProjection kpi = kpi(0, true);
        given(newsRepository.findKpis(eq(CORP_CODE), any(), any())).willReturn(kpi);

        assertThat(service.getStats(CORP_CODE, 7, 30).kpis().importantIssueCount()).isZero();
    }

    @Test
    @DisplayName("없는 기업은 세 조회 모두 COMPANY_NOT_FOUND 다")
    void unknownCompanyThrowsForAllThree() {
        given(companyRepository.existsById("00000000")).willReturn(false);

        assertThatThrownBy(() -> service.getNews("00000000", 7, "latest", 1, 6))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.COMPANY_NOT_FOUND);
        assertThatThrownBy(() -> service.getTopNews("00000000", 30, 3))
                .isInstanceOf(BusinessException.class);
        assertThatThrownBy(() -> service.getStats("00000000", 7, 30))
                .isInstanceOf(BusinessException.class);
    }

    @Test
    @DisplayName("없는 기업은 정렬값 검증보다 먼저 404 다")
    void unknownCompanyThrowsBeforeSortCheck() {
        given(companyRepository.existsById("00000000")).willReturn(false);

        assertThatThrownBy(() -> service.getNews("00000000", 7, "popular", 1, 6))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.COMPANY_NOT_FOUND);
    }

    private static NewsItemProjection news(long id, String title, String publishedAt, String score) {
        NewsItemProjection projection = mock(NewsItemProjection.class);
        given(projection.getId()).willReturn(id);
        given(projection.getTitle()).willReturn(title);
        given(projection.getPublishedAt()).willReturn(LocalDate.parse(publishedAt));
        given(projection.getOriginalUrl()).willReturn("https://news.example.com/" + id);
        given(projection.getImportanceScore()).willReturn(score == null ? null : new BigDecimal(score));
        return projection;
    }

    private static TopNewsProjection top(long id, String title, String score) {
        TopNewsProjection projection = mock(TopNewsProjection.class);
        given(projection.getId()).willReturn(id);
        given(projection.getTitle()).willReturn(title);
        given(projection.getImportanceScore()).willReturn(new BigDecimal(score));
        return projection;
    }

    private static NewsKpiProjection kpi(long important, Boolean scored) {
        NewsKpiProjection projection = mock(NewsKpiProjection.class);
        given(projection.getImportantCount()).willReturn(important);
        given(projection.getScored()).willReturn(scored);
        return projection;
    }
}

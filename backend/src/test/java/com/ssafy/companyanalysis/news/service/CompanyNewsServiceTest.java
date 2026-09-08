package com.ssafy.companyanalysis.news.service;

import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.news.dto.CompanyNewsResponse;
import com.ssafy.companyanalysis.news.dto.NewsStatsResponse;
import com.ssafy.companyanalysis.news.dto.TopNewsResponse;
import com.ssafy.companyanalysis.news.repository.CategoryCountProjection;
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
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

/**
 * 기간 계산과 KPI·분포의 파생값을 검증한다.
 *
 * <p>뉴스 수집과 AI 분석이 아직 PoC 단계라 값은 없지만, "분석이 안 돌았다"와 "그런 일이
 * 없었다"를 가르는 규칙은 값이 들어오기 전에 고정해 두어야 한다. 나중에 값만 채워졌을 때
 * 화면 표시가 달라지지 않게 하려는 것이다.
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
    @DisplayName("목록은 기본 필드와 AI 필드를 그대로 옮기고 total 을 함께 싣는다")
    void mapsNewsItemsAndTotal() {
        List<NewsItemProjection> rows = List.of(
                news(10250, "1분기 영업이익 6.6조 원", "메모리 가격 회복", "2025-05-20", "실적", "메모리", "9.6"),
                news(10241, "텍사스 파운드리 공장 건설", null, "2025-05-13", null, null, null));
        Page<NewsItemProjection> page = new PageImpl<>(rows, PageRequest.of(0, 6), 48);
        given(newsRepository.findNews(eq(CORP_CODE), any(), isNull(), anyBoolean(), any()))
                .willReturn(page);

        CompanyNewsResponse response = service.getNews(CORP_CODE, null, 7, "latest", 1, 6);

        assertThat(response.total()).isEqualTo(48);
        assertThat(response.items()).hasSize(2);
        assertThat(response.items().get(0).id()).isEqualTo(10250);
        assertThat(response.items().get(0).publishedAt()).isEqualTo(LocalDate.of(2025, 5, 20));
        assertThat(response.items().get(0).importanceScore()).isEqualByComparingTo("9.6");
        // AI 분석이 실패한 뉴스도 목록에 남고 AI 필드만 null 이다.
        assertThat(response.items().get(1).title()).isEqualTo("텍사스 파운드리 공장 건설");
        assertThat(response.items().get(1).category()).isNull();
        assertThat(response.items().get(1).importanceScore()).isNull();
    }

    @Test
    @DisplayName("정렬값에 따라 중요도 우선 여부를 조회에 넘긴다")
    void passesSortFlagToQuery() {
        given(newsRepository.findNews(anyString(), any(), any(), anyBoolean(), any()))
                .willReturn(Page.empty());

        service.getNews(CORP_CODE, null, 7, "importance", 1, 6);
        verify(newsRepository).findNews(eq(CORP_CODE), any(), isNull(), eq(true), any());

        service.getNews(CORP_CODE, null, 7, "latest", 1, 6);
        verify(newsRepository).findNews(eq(CORP_CODE), any(), isNull(), eq(false), any());
    }

    @Test
    @DisplayName("기간은 주입한 시계에서 계산한다 (7일 전)")
    void computesSinceFromClock() {
        given(newsRepository.findNews(anyString(), any(), any(), anyBoolean(), any()))
                .willReturn(Page.empty());

        service.getNews(CORP_CODE, null, 7, "latest", 1, 6);

        OffsetDateTime expected = OffsetDateTime.now(FIXED_CLOCK).minusDays(7);
        verify(newsRepository).findNews(eq(CORP_CODE), eq(expected), isNull(), anyBoolean(), any());
    }

    @Test
    @DisplayName("모르는 정렬값은 조용히 최신순으로 넘기지 않고 400 이다")
    void unknownSortIsBadRequest() {
        assertThatThrownBy(() -> service.getNews(CORP_CODE, null, 7, "popular", 1, 6))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.INVALID_PARAMETER);

        verify(newsRepository, never()).findNews(anyString(), any(), any(), anyBoolean(), any());
    }

    @Test
    @DisplayName("뉴스가 없으면 오류가 아니라 빈 배열과 total 0 이다")
    void emptyNewsIsNotAnError() {
        given(newsRepository.findNews(anyString(), any(), any(), anyBoolean(), any()))
                .willReturn(Page.empty());

        CompanyNewsResponse response = service.getNews(CORP_CODE, null, 7, "latest", 1, 6);

        assertThat(response.items()).isEmpty();
        assertThat(response.total()).isZero();
    }

    @Test
    @DisplayName("상위 뉴스는 조회 순서대로 1 부터 순위를 매긴다")
    void ranksTopNewsFromOne() {
        List<TopNewsProjection> rows = List.of(
                top(10250, "실적 발표", "실적", "9.6"),
                top(10241, "공장 건설", "투자", "9.2"),
                top(10238, "HBM4 공급", "기술", "8.8"));
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
        NewsKpiProjection kpi = kpi(12, 5, 7, true);
        given(newsRepository.findKpis(eq(CORP_CODE), any(), any(), anyString(), anyString()))
                .willReturn(kpi);
        given(newsRepository.countNews(eq(CORP_CODE), any())).willReturn(48L);

        NewsStatsResponse response = service.getStats(CORP_CODE, 7, 30);

        assertThat(response.kpis().recentNewsCount()).isEqualTo(48);
        assertThat(response.kpis().recentNewsDays()).isEqualTo(7);
        assertThat(response.kpis().importantIssueCount()).isEqualTo(12);
        assertThat(response.kpis().investmentIssueCount()).isEqualTo(5);
        assertThat(response.kpis().techIssueCount()).isEqualTo(7);
        assertThat(response.kpis().issueDays()).isEqualTo(30);
        // 뉴스 수는 newsDays, 이슈는 issueDays 로 각각 조회한다.
        verify(newsRepository).countNews(CORP_CODE, OffsetDateTime.now(FIXED_CLOCK).minusDays(7));
        verify(newsRepository).findKpis(eq(CORP_CODE), eq(OffsetDateTime.now(FIXED_CLOCK).minusDays(30)),
                any(), anyString(), anyString());
    }

    @Test
    @DisplayName("AI 분석이 안 돌았으면 이슈 KPI 세 건은 0 이 아니라 null 이다")
    void unscoredIssueKpisAreNullNotZero() {
        NewsKpiProjection kpi = kpi(0, 0, 0, false);
        given(newsRepository.findKpis(eq(CORP_CODE), any(), any(), anyString(), anyString()))
                .willReturn(kpi);
        given(newsRepository.countNews(eq(CORP_CODE), any())).willReturn(48L);

        NewsStatsResponse.Kpis kpis = service.getStats(CORP_CODE, 7, 30).kpis();

        // 뉴스는 수집됐으니 뉴스 수는 나간다. 중요도 기반 값만 미제공이다.
        assertThat(kpis.recentNewsCount()).isEqualTo(48);
        assertThat(kpis.importantIssueCount()).isNull();
        assertThat(kpis.investmentIssueCount()).isNull();
        assertThat(kpis.techIssueCount()).isNull();
    }

    @Test
    @DisplayName("분석은 돌았는데 중요 이슈가 없으면 null 이 아니라 0 이다")
    void scoredButNoImportantIssueIsZero() {
        NewsKpiProjection kpi = kpi(0, 0, 0, true);
        given(newsRepository.findKpis(eq(CORP_CODE), any(), any(), anyString(), anyString()))
                .willReturn(kpi);

        NewsStatsResponse.Kpis kpis = service.getStats(CORP_CODE, 7, 30).kpis();

        assertThat(kpis.importantIssueCount()).isZero();
        assertThat(kpis.investmentIssueCount()).isZero();
    }

    @Test
    @DisplayName("분포 비율은 분류된 뉴스 대비 백분율이라 합이 100 이다")
    void distributionRatiosSumToHundred() {
        NewsKpiProjection kpi = kpi(0, 0, 0, true);
        given(newsRepository.findKpis(eq(CORP_CODE), any(), any(), anyString(), anyString()))
                .willReturn(kpi);
        List<CategoryCountProjection> rows =
                List.of(category("기술", 28), category("투자", 20), category("실적", 2));
        given(newsRepository.countByCategory(eq(CORP_CODE), any())).willReturn(rows);

        NewsStatsResponse.Distribution distribution = service.getStats(CORP_CODE, 7, 30).distribution();

        assertThat(distribution.days()).isEqualTo(30);
        assertThat(distribution.total()).isEqualTo(50);
        assertThat(distribution.byCategory()).extracting(NewsStatsResponse.CategoryCount::ratio)
                .containsExactly(new BigDecimal("56.0"), new BigDecimal("40.0"), new BigDecimal("4.0"));
    }

    @Test
    @DisplayName("분류된 뉴스가 없으면 분포 합계는 0 이 아니라 null 이고 목록은 빈 배열이다")
    void emptyDistributionHasNullTotal() {
        NewsKpiProjection kpi = kpi(0, 0, 0, true);
        given(newsRepository.findKpis(eq(CORP_CODE), any(), any(), anyString(), anyString()))
                .willReturn(kpi);
        given(newsRepository.countByCategory(eq(CORP_CODE), any())).willReturn(List.of());

        NewsStatsResponse.Distribution distribution = service.getStats(CORP_CODE, 7, 30).distribution();

        assertThat(distribution.total()).isNull();
        assertThat(distribution.byCategory()).isEmpty();
        // 기간은 값이 없어도 되돌려준다. 화면이 "최근 30일"을 표시해야 한다.
        assertThat(distribution.days()).isEqualTo(30);
    }

    @Test
    @DisplayName("없는 기업은 세 조회 모두 COMPANY_NOT_FOUND 다")
    void unknownCompanyThrowsForAllThree() {
        given(companyRepository.existsById("00000000")).willReturn(false);

        assertThatThrownBy(() -> service.getNews("00000000", null, 7, "latest", 1, 6))
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

        assertThatThrownBy(() -> service.getNews("00000000", null, 7, "popular", 1, 6))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.COMPANY_NOT_FOUND);
    }

    private static NewsItemProjection news(long id, String title, String description,
                                           String publishedAt, String category,
                                           String relatedBusiness, String score) {
        NewsItemProjection projection = mock(NewsItemProjection.class);
        given(projection.getId()).willReturn(id);
        given(projection.getTitle()).willReturn(title);
        given(projection.getDescription()).willReturn(description);
        given(projection.getPublishedAt()).willReturn(LocalDate.parse(publishedAt));
        given(projection.getOriginalUrl()).willReturn("https://news.example.com/" + id);
        given(projection.getCategory()).willReturn(category);
        given(projection.getRelatedBusiness()).willReturn(relatedBusiness);
        given(projection.getImportanceScore()).willReturn(score == null ? null : new BigDecimal(score));
        return projection;
    }

    private static TopNewsProjection top(long id, String title, String category, String score) {
        TopNewsProjection projection = mock(TopNewsProjection.class);
        given(projection.getId()).willReturn(id);
        given(projection.getTitle()).willReturn(title);
        given(projection.getCategory()).willReturn(category);
        given(projection.getImportanceScore()).willReturn(new BigDecimal(score));
        return projection;
    }

    private static NewsKpiProjection kpi(long important, long investment, long tech, Boolean scored) {
        NewsKpiProjection projection = mock(NewsKpiProjection.class);
        given(projection.getImportantCount()).willReturn(important);
        given(projection.getInvestmentCount()).willReturn(investment);
        given(projection.getTechCount()).willReturn(tech);
        given(projection.getScored()).willReturn(scored);
        return projection;
    }

    private static CategoryCountProjection category(String name, long count) {
        CategoryCountProjection projection = mock(CategoryCountProjection.class);
        given(projection.getCategory()).willReturn(name);
        given(projection.getCount()).willReturn(count);
        return projection;
    }
}

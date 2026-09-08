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
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Clock;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Set;
import java.util.stream.IntStream;

@Service
public class CompanyNewsService {

    private static final BigDecimal HUNDRED = BigDecimal.valueOf(100);

    /** 분포 비율 소수 자릿수. 프론트 목업이 29.2 라 1자리다. */
    private static final int RATIO_SCALE = 1;

    /** 명세가 정한 정렬값. 프론트도 같은 두 값을 보낸다. */
    private static final String SORT_LATEST = "latest";
    private static final String SORT_IMPORTANCE = "importance";
    private static final Set<String> SORTS = Set.of(SORT_LATEST, SORT_IMPORTANCE);

    /**
     * "중요 이슈"의 기준 점수. <b>임시값이다.</b>
     *
     * <p>명세도 프론트도 이 경계를 적어 두지 않았다. AI 중요도 분석 PoC(S15P21A504-92)가
     * 점수 분포를 내면 그 결과로 확정해야 한다. 0.0~10.0 척도에서 상위권만 남기는 값으로
     * 7.0 을 잡아 두었다.
     *
     * <p>한 군데에만 두는 것은 확정될 때 한 줄만 고치면 되게 하려는 것이다. 값이 바뀌면
     * 중요 이슈 수와 투자·기술 이슈 수 세 개가 함께 움직인다.
     */
    private static final BigDecimal IMPORTANT_SCORE_THRESHOLD = new BigDecimal("7.0");

    /**
     * KPI 로 따로 세는 카테고리 둘. 프론트가 아는 어휘를 그대로 쓴다.
     *
     * <p>화면의 KPI 네 장이 최근 뉴스 수 · 중요 이슈 수 · 투자 이슈 · 기술 이슈다. 뒤의 둘은
     * 중요 이슈 안에서 센 값이다 — 프론트 목업이 중요 이슈 12건에 투자 5 · 기술 7 로 되어 있다.
     * 카테고리 전체 건수는 분포가 따로 준다.
     */
    private static final String CATEGORY_INVESTMENT = "투자";
    private static final String CATEGORY_TECH = "기술";

    private final CompanyRepository companyRepository;
    private final CompanyNewsRepository companyNewsRepository;
    private final Clock clock;

    public CompanyNewsService(CompanyRepository companyRepository,
                              CompanyNewsRepository companyNewsRepository,
                              Clock clock) {
        this.companyRepository = companyRepository;
        this.companyNewsRepository = companyNewsRepository;
        this.clock = clock;
    }

    /**
     * 뉴스 목록을 조회한다. 없는 기업은 404 COMPANY_NOT_FOUND 다.
     *
     * <p>뉴스가 없는 것은 오류가 아니다. 아직 수집되지 않은 기업도 있고 조용한 기업도 있다.
     *
     * @param category null 이면 전체. 값이 있으면 그 카테고리만
     * @param sort     latest 또는 importance. 그 밖의 값은 400 INVALID_PARAMETER
     * @param page     1부터 시작하는 페이지 번호
     */
    @Transactional(readOnly = true)
    public CompanyNewsResponse getNews(String corpCode, String category, int days,
                                       String sort, int page, int size) {
        requireCompany(corpCode);
        requireKnownSort(sort);

        Page<NewsItemProjection> found = companyNewsRepository.findNews(
                corpCode, since(days), category, SORT_IMPORTANCE.equals(sort),
                PageRequest.of(page - 1, size));

        List<CompanyNewsResponse.Item> items = found.getContent().stream()
                .map(projection -> new CompanyNewsResponse.Item(
                        projection.getId(),
                        projection.getTitle(),
                        projection.getDescription(),
                        projection.getPublishedAt(),
                        projection.getOriginalUrl(),
                        projection.getCategory(),
                        projection.getRelatedBusiness(),
                        projection.getImportanceScore()))
                .toList();

        return new CompanyNewsResponse(items, found.getTotalElements());
    }

    /**
     * 중요 뉴스 상위 N 건을 조회한다. 없는 기업은 404 COMPANY_NOT_FOUND 다.
     *
     * <p>순위는 조회 순서대로 1부터 매긴다. 중요도가 없는 뉴스는 조회에서 이미 빠졌으므로
     * 뉴스가 있어도 이 목록은 빌 수 있다.
     */
    @Transactional(readOnly = true)
    public TopNewsResponse getTopNews(String corpCode, int days, int limit) {
        requireCompany(corpCode);

        List<TopNewsProjection> rows = companyNewsRepository.findTopNews(corpCode, since(days), limit);

        return new TopNewsResponse(IntStream.range(0, rows.size())
                .mapToObj(i -> {
                    TopNewsProjection row = rows.get(i);
                    return new TopNewsResponse.Item(i + 1, row.getId(), row.getTitle(),
                            row.getCategory(), row.getImportanceScore());
                })
                .toList());
    }

    /**
     * 뉴스 KPI와 이슈 분포를 조회한다. 없는 기업은 404 COMPANY_NOT_FOUND 다.
     *
     * <p>두 기간을 쓴다. 뉴스 수는 {@code newsDays}, 이슈 관련 값과 분포는 {@code issueDays} 다.
     * 요청받은 기간을 응답에 되돌려주는 것은 화면이 "7일 기준"처럼 함께 표시하기 때문이다.
     */
    @Transactional(readOnly = true)
    public NewsStatsResponse getStats(String corpCode, int newsDays, int issueDays) {
        requireCompany(corpCode);

        OffsetDateTime issueSince = since(issueDays);
        NewsKpiProjection kpi = companyNewsRepository.findKpis(
                corpCode, issueSince, IMPORTANT_SCORE_THRESHOLD, CATEGORY_INVESTMENT, CATEGORY_TECH);

        return new NewsStatsResponse(
                new NewsStatsResponse.Kpis(
                        companyNewsRepository.countNews(corpCode, since(newsDays)),
                        newsDays,
                        scoredCount(kpi, NewsKpiProjection::getImportantCount),
                        scoredCount(kpi, NewsKpiProjection::getInvestmentCount),
                        scoredCount(kpi, NewsKpiProjection::getTechCount),
                        issueDays),
                distribution(corpCode, issueSince, issueDays));
    }

    private void requireCompany(String corpCode) {
        if (!companyRepository.existsById(corpCode)) {
            throw new BusinessException(ErrorCode.COMPANY_NOT_FOUND);
        }
    }

    /**
     * 모르는 정렬값은 400 이다. latest 로 조용히 넘기지 않는다.
     *
     * <p>오타를 낸 호출자는 자기가 중요도순을 보고 있다고 믿는데 화면에는 최신순이 나온다.
     * 지표 슬러그 검증과 같은 판단이다.
     */
    private void requireKnownSort(String sort) {
        if (!SORTS.contains(sort)) {
            throw new BusinessException(ErrorCode.INVALID_PARAMETER, "지원하지 않는 정렬 기준입니다.");
        }
    }

    /**
     * 조회 기준 시각. 지금으로부터 {@code days} 일 전이다.
     *
     * <p>시계를 주입받는 이유는 테스트다. SQL 안에서 {@code now()} 를 쓰면 "7일 전 기사가
     * 걸리는지"를 확인할 방법이 없고, 서버 표준시가 UTC 면 하루 경계가 서울과 어긋난다.
     * 기준연도 계산이 같은 시계를 쓴다.
     */
    private OffsetDateTime since(int days) {
        return OffsetDateTime.now(clock).minusDays(days);
    }

    /**
     * 중요도 기반 KPI 한 건. 기간 내에 중요도가 매겨진 뉴스가 하나도 없으면 null 이다.
     *
     * <p>0 을 내보내지 않는다. "그 기간에 중요한 일이 없었다"와 "AI 분석이 아직 안 돌았다"는
     * 다른 사실인데, 둘 다 0 으로 나가면 화면이 구분할 수 없다. 앞의 것은 0, 뒤의 것은 null 이고
     * 화면은 null 을 "미제공"으로 표시한다(docs/decisions/0001-missing-data-response.md 규칙 3).
     */
    private Long scoredCount(NewsKpiProjection kpi,
                             java.util.function.ToLongFunction<NewsKpiProjection> count) {
        return Boolean.TRUE.equals(kpi.getScored()) ? count.applyAsLong(kpi) : null;
    }

    /**
     * 카테고리 분포. 분류된 뉴스가 하나도 없으면 합계는 null 이고 목록은 빈 배열이다.
     *
     * <p>합계를 분류된 건수로 잡는 것은 비율의 분모가 그것이어야 조각의 합이 100 이 되기
     * 때문이다. 분류하지 못한 뉴스를 분모에 넣으면 도넛이 다 차지 않는데, 화면에는 그
     * 빈자리를 설명할 조각이 없다.
     */
    private NewsStatsResponse.Distribution distribution(String corpCode, OffsetDateTime since, int days) {
        List<CategoryCountProjection> rows = companyNewsRepository.countByCategory(corpCode, since);
        if (rows.isEmpty()) {
            return new NewsStatsResponse.Distribution(days, null, List.of());
        }

        long total = rows.stream().mapToLong(CategoryCountProjection::getCount).sum();
        List<NewsStatsResponse.CategoryCount> byCategory = rows.stream()
                .map(row -> new NewsStatsResponse.CategoryCount(
                        row.getCategory(), row.getCount(), ratio(row.getCount(), total)))
                .toList();

        return new NewsStatsResponse.Distribution(days, total, byCategory);
    }

    /** 분류된 뉴스 대비 백분율. 분모는 항상 1 이상이라 나눌 수 없는 경우가 없다. */
    private BigDecimal ratio(long count, long total) {
        return BigDecimal.valueOf(count)
                .multiply(HUNDRED)
                .divide(BigDecimal.valueOf(total), RATIO_SCALE, RoundingMode.HALF_UP);
    }
}

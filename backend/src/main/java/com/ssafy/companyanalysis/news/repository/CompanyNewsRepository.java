package com.ssafy.companyanalysis.news.repository;

import com.ssafy.companyanalysis.company.domain.Company;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;

/**
 * 최근 이슈 API 세 건이 쓰는 조회 전용 리포지토리.
 *
 * <p>기간은 모두 "이 시각 이후"로 받는다. 서비스가 Clock 으로 기준 시각을 만들어 넘긴다.
 * SQL 안에서 {@code now()} 를 쓰면 테스트가 시계를 갈아끼울 수 없고, 서버 표준시가 UTC 일 때
 * 하루 경계가 서울과 어긋난다.
 *
 * <p>발행 시각을 모르는 뉴스는 어느 조회에도 걸리지 않는다. 세 API 가 모두 기간으로 좁히고,
 * 언제 나온 기사인지 모르면 그 기간에 속하는지 판단할 수 없다.
 *
 * <p>날짜는 서울 기준으로 잘라 내보낸다. 저장은 시각까지 하지만 화면이 날짜만 보여주고,
 * 시각을 그대로 주면 프론트가 표준시 변환을 다시 해야 한다.
 *
 * <p>별칭을 큰따옴표로 감싼 것은 PostgreSQL 이 따옴표 없는 식별자를 소문자로 접어
 * 프로젝션의 getter 와 어긋나기 때문이다.
 *
 * <p>V16 에서 news_category · description · related_business 가 사라졌다. 카테고리로
 * 자르던 조회(목록 필터 · 투자·기술 KPI · 분포)는 근거가 없어져 함께 없앴고, 남은 분류
 * 축은 중요도 하나다.
 */
public interface CompanyNewsRepository extends Repository<Company, String> {

    /**
     * 뉴스 목록.
     *
     * <p>정렬은 {@code Pageable} 이 아니라 쿼리가 정한다. 명세의 정렬값(latest·importance)이
     * 컬럼 이름과 1:1 이 아니고, 같은 값이 겹칠 때의 2·3차 기준까지 정해 두어야 페이지를
     * 넘길 때 같은 기사가 두 번 나오거나 빠지는 일이 없다.
     *
     * <p>중요도순에서 중요도가 없는 뉴스를 버리지 않고 뒤로 보낸다. 목록은 분석 실패한
     * 뉴스도 보여주는 자리이고, 정렬 기준이 없는 것과 목록에서 빠지는 것은 다르다.
     *
     * <p>{@code cast} 가 붙은 것은 PostgreSQL 때문이다. 네이티브 쿼리의 파라미터에 null 이
     * 들어가면 타입을 못 정해 조회가 실패한다.
     */
    @Query(value = """
            SELECT n.id                                              AS "id",
                   n.title                                           AS "title",
                   (n.published_at AT TIME ZONE 'Asia/Seoul')::date  AS "publishedAt",
                   n.original_url                                    AS "originalUrl",
                   n.importance_score                                AS "importanceScore"
            FROM news_article n
            WHERE n.corp_code    = :corpCode
              AND n.published_at IS NOT NULL
              AND n.published_at >= :since
            ORDER BY CASE WHEN cast(:importanceFirst AS boolean) THEN n.importance_score END DESC NULLS LAST,
                     n.published_at DESC,
                     n.id DESC
            """,
            countQuery = """
            SELECT count(*)
            FROM news_article n
            WHERE n.corp_code    = :corpCode
              AND n.published_at IS NOT NULL
              AND n.published_at >= :since
            """,
            nativeQuery = true)
    Page<NewsItemProjection> findNews(@Param("corpCode") String corpCode,
                                      @Param("since") OffsetDateTime since,
                                      @Param("importanceFirst") boolean importanceFirst,
                                      Pageable pageable);

    /**
     * 중요도 상위 뉴스. 중요도가 없는 뉴스는 순위를 매길 수 없어 아예 제외한다.
     *
     * <p>목록 조회가 같은 뉴스를 뒤로 보내는 것과 규칙이 다르다. 목록은 "이 기업의 최근
     * 뉴스"라서 분석 실패한 기사도 보여줘야 하지만, 이쪽은 "중요한 뉴스 셋"이라 근거 없는
     * 기사를 끼워 넣으면 목록의 뜻이 사라진다.
     *
     * <p>동점이면 최신 기사가 앞이고, 그마저 같으면 적재 순서를 쓴다. 순위를 화면에 숫자로
     * 보여주므로 새로 고칠 때마다 1위가 바뀌면 안 된다.
     */
    @Query(value = """
            SELECT n.id               AS "id",
                   n.title            AS "title",
                   n.importance_score AS "importanceScore"
            FROM news_article n
            WHERE n.corp_code        = :corpCode
              AND n.published_at    IS NOT NULL
              AND n.published_at    >= :since
              AND n.importance_score IS NOT NULL
            ORDER BY n.importance_score DESC, n.published_at DESC, n.id DESC
            LIMIT :limit
            """, nativeQuery = true)
    List<TopNewsProjection> findTopNews(@Param("corpCode") String corpCode,
                                        @Param("since") OffsetDateTime since,
                                        @Param("limit") int limit);

    /** 기간 내 뉴스 수. 중요도와 무관하게 전부 센다. */
    @Query(value = """
            SELECT count(*)
            FROM news_article
            WHERE corp_code    = :corpCode
              AND published_at IS NOT NULL
              AND published_at >= :since
            """, nativeQuery = true)
    long countNews(@Param("corpCode") String corpCode, @Param("since") OffsetDateTime since);

    /**
     * 중요 이슈 수와 "중요도가 매겨진 뉴스가 있었나"를 한 번에 센다.
     *
     * <p>{@code scored} 가 없으면 건수가 0 으로 나오는데, 그것이 "중요한 일이 없었다"인지
     * "분석이 아직 안 돌았다"인지 구분할 수 없다. 그래서 중요도가 매겨진 뉴스의 존재를 함께
     * 물어보고, 없으면 서비스가 값을 null 로 바꾼다.
     */
    @Query(value = """
            SELECT count(*) FILTER (WHERE importance_score >= :threshold) AS "importantCount",
                   bool_or(importance_score IS NOT NULL)                  AS "scored"
            FROM news_article
            WHERE corp_code    = :corpCode
              AND published_at IS NOT NULL
              AND published_at >= :since
            """, nativeQuery = true)
    NewsKpiProjection findKpis(@Param("corpCode") String corpCode,
                               @Param("since") OffsetDateTime since,
                               @Param("threshold") BigDecimal threshold);
}

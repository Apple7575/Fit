package com.ssafy.companyanalysis.company.repository;

import com.ssafy.companyanalysis.company.domain.Company;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Optional;

public interface CompanyRepository extends JpaRepository<Company, String> {

    /**
     * corpCode 로 기업 상세를 조회한다(분석 페이지 헤더용).
     *
     * <p>산업 정보가 없는 기업도 빠지면 안 되므로 LEFT JOIN 이다. market 은 corp_cls 에서
     * 파생하므로 원본을 그대로 실어 서비스에서 변환한다. 검색 쿼리와 마찬가지로 별칭을
     * 큰따옴표로 감싸 프로젝션 getter 와 대소문자를 맞춘다.
     *
     * <p>dataYear 는 기업 단위 최신 적재 연도다. 상세·지표·산업비교가 저마다 기준연도를
     * 정하면 한 화면에 다른 해가 섞이므로, year 를 주지 않았을 때의 기준을 여기 하나로 모은다.
     * company_metric_timeseries_idx 의 선두가 corp_code 라 max 는 인덱스로 끝난다.
     */
    @Query(value = """
            SELECT c.corp_code       AS "corpCode",
                   c.corp_name       AS "corpName",
                   c.stock_code      AS "stockCode",
                   i.industry_code   AS "industryCode",
                   i.industry_name   AS "industryName",
                   c.corp_cls        AS "corpCls",
                   c.ceo_nm          AS "ceoNm",
                   c.established_date AS "establishedDate",
                   (SELECT max(cm.fiscal_year)
                      FROM company_metric cm
                     WHERE cm.corp_code = c.corp_code) AS "dataYear"
            FROM company c
            LEFT JOIN industry i ON i.industry_code = c.industry_code
            WHERE c.corp_code = :corpCode
            """, nativeQuery = true)
    Optional<CompanyDetailProjection> findDetailByCorpCode(@Param("corpCode") String corpCode);

    /**
     * 기업명 부분일치 또는 종목코드 완전일치로 검색한다.
     *
     * <p>네이티브 쿼리를 쓰는 이유는 {@code ILIKE} 때문이다. JPQL 의
     * {@code LOWER(x) LIKE LOWER(y)} 는 corp_name 에 걸어 둔 trgm GIN 인덱스를
     * 타지 못하지만, PostgreSQL 의 {@code ILIKE} 는 gin_trgm_ops 인덱스를 그대로 쓴다.
     *
     * <p>산업 정보가 없는 기업도 결과에서 빠지면 안 되므로 LEFT JOIN 이다.
     * 별칭을 큰따옴표로 감싼 것은 PostgreSQL 이 따옴표 없는 식별자를 소문자로 접어
     * 프로젝션의 getter 와 어긋나기 때문이다.
     */
    default Page<CompanySummaryProjection> search(String keyword, Pageable pageable) {
        return searchByKeyword(escapeLikePattern(keyword), keyword, pageable);
    }

    @Query(value = """
            SELECT c.corp_code     AS "corpCode",
                   c.corp_name     AS "corpName",
                   c.stock_code    AS "stockCode",
                   i.industry_code AS "industryCode",
                   i.industry_name AS "industryName"
            FROM company c
            LEFT JOIN industry i ON i.industry_code = c.industry_code
            WHERE c.corp_name ILIKE '%' || :likeKeyword || '%' ESCAPE '\\'
               OR c.stock_code = :keyword
            ORDER BY c.corp_name
            """,
            countQuery = """
            SELECT count(*)
            FROM company c
            WHERE c.corp_name ILIKE '%' || :likeKeyword || '%' ESCAPE '\\'
               OR c.stock_code = :keyword
            """,
            nativeQuery = true)
    Page<CompanySummaryProjection> searchByKeyword(@Param("likeKeyword") String likeKeyword,
                                                  @Param("keyword") String keyword,
                                                  Pageable pageable);

    /**
     * 검색어의 LIKE 메타문자를 리터럴로 바꾼다. 이스케이프하지 않으면 {@code %} 하나로
     * 전체 테이블이 매치되어 trgm 인덱스를 못 타고, {@code 삼성_전자} 가 {@code 삼성X전자} 에도 걸린다.
     * 종목코드 완전일치에는 원본 검색어를 그대로 써야 하므로 파라미터를 분리한다.
     */
    private static String escapeLikePattern(String keyword) {
        return keyword.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_");
    }
}

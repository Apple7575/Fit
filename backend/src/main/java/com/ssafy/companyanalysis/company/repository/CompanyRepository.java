package com.ssafy.companyanalysis.company.repository;

import com.ssafy.companyanalysis.company.domain.Company;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface CompanyRepository extends JpaRepository<Company, String> {

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
    @Query(value = """
            SELECT c.corp_code     AS "corpCode",
                   c.corp_name     AS "corpName",
                   c.stock_code    AS "stockCode",
                   i.industry_code AS "industryCode",
                   i.industry_name AS "industryName"
            FROM company c
            LEFT JOIN industry i ON i.industry_code = c.industry_code
            WHERE c.corp_name ILIKE '%' || :keyword || '%'
               OR c.stock_code = :keyword
            ORDER BY c.corp_name
            """,
            countQuery = """
            SELECT count(*)
            FROM company c
            WHERE c.corp_name ILIKE '%' || :keyword || '%'
               OR c.stock_code = :keyword
            """,
            nativeQuery = true)
    Page<CompanySummaryProjection> search(@Param("keyword") String keyword, Pageable pageable);
}

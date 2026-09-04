package com.ssafy.companyanalysis.comparison.repository;

import com.ssafy.companyanalysis.company.domain.Industry;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface IndustryCompanyRepository extends Repository<Industry, String> {

    /** 산업 코드가 카탈로그에 있는지 확인한다. 없으면 빈 목록을 200 으로 내보내기 위해 쓴다. */
    Optional<Industry> findByIndustryCode(String industryCode);

    /**
     * 같은 KSIC 중분류의 비교 후보 기업을 정렬 지표 기준 내림차순으로 조회한다.
     *
     * <p>정렬 기준 연도를 파라미터로 받지 않고 서브쿼리로 정하는 이유는, 이 응답에 기준연도가
     * 나가지 않기 때문이다. 호출자가 연도를 모르는 채 목록만 받아 가므로 "산업 안에서 그 지표의
     * 값이 있는 가장 최근 해"를 서버가 정한다. 기업마다 제 최신연도를 쓰면 2024년 매출과
     * 2025년 매출이 한 목록에서 섞여 순위가 뒤집힌다.
     *
     * <p>지표값을 LEFT JOIN 하므로 값이 없는 기업도 목록에서 빠지지 않는다. 후보 목록은
     * 사용자가 비교할 기업을 고르는 곳이라, 값이 아직 안 들어온 기업을 숨기면 고를 방법이
     * 사라진다. 값이 없는 기업은 {@code NULLS LAST} 로 뒤에 붙고 이름순으로 정렬된다.
     *
     * <p>적재된 값이 하나도 없으면 서브쿼리가 null 이라 조인 조건이 어느 행에도 맞지 않는다.
     * 그때는 전부 이름순이 된다 — 빈 목록이 아니라 순서만 이름순인 목록이다.
     *
     * <p>별칭을 큰따옴표로 감싼 것은 PostgreSQL 이 따옴표 없는 식별자를 소문자로 접어
     * 프로젝션의 getter 와 어긋나기 때문이다.
     */
    @Query(value = """
            SELECT c.corp_code AS "corpCode",
                   c.corp_name AS "corpName"
            FROM company c
            LEFT JOIN company_metric cm
                   ON cm.corp_code   = c.corp_code
                  AND cm.metric_code = :sortMetric
                  AND cm.fiscal_year = (SELECT max(cm2.fiscal_year)
                                          FROM company_metric cm2
                                          JOIN company c2 ON c2.corp_code = cm2.corp_code
                                         WHERE c2.industry_code = :industryCode
                                           AND cm2.metric_code  = :sortMetric)
            WHERE c.industry_code = :industryCode
            ORDER BY cm.metric_value DESC NULLS LAST, c.corp_name
            LIMIT :limit
            """, nativeQuery = true)
    List<IndustryCompanyProjection> findCandidates(@Param("industryCode") String industryCode,
                                                   @Param("sortMetric") String sortMetric,
                                                   @Param("limit") int limit);
}

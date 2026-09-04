package com.ssafy.companyanalysis.comparison.repository;

import com.ssafy.companyanalysis.company.domain.Company;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;

public interface IndustryComparisonRepository extends Repository<Company, String> {

    /**
     * 지정한 기업들의 두 해치 지표값을 조회한다(v2).
     *
     * <p>v1 은 같은 산업 기업을 전부 읽었다. v2 명세가 "산업 전체 자동 비교"를 "사용자가 고른
     * peers(최대 3) 비교"로 바꾸면서, 대상 기업과 고른 기업의 corp_code 만 받는다. 산업 전체를
     * 읽고 자바에서 걸러내면 기업이 많은 산업에서 쓰지 않을 행을 전부 끌고 오게 된다.
     *
     * <p>연도를 둘 받는 것은 매출 성장률 때문이다. 성장률은 요청 연도와 전년 매출이 함께
     * 있어야 나오므로, 두 해를 한 쿼리로 가져오고 서비스가 {@code fiscalYear} 로 가른다.
     * 성장률을 요청하지 않아도 전년 행을 함께 읽는데, 그 대가는 기업 4곳 × 지표 몇 개의
     * 행 몇 개라서 쿼리를 둘로 나눠 얻을 이득보다 작다.
     *
     * <p>기업을 기준으로 지표값을 LEFT JOIN 하므로, 값이 없는 기업도 결과에서 빠지지 않는다
     * (F-12·F-20). 존재하지 않는 corp_code 는 company 에 행이 없어 자연스럽게 빠진다 —
     * 낡은 후보 목록에서 고른 기업 하나 때문에 비교 전체가 실패하지 않게 하려는 것이다.
     *
     * <p>value_scale 은 응답 직렬화 자릿수를 맞추기 위해 metric 에서 함께 가져온다.
     * 정렬은 corp_name 기준이며 대상 기업 우선 배치는 서비스가 한다.
     */
    @Query(value = """
            SELECT c.corp_code     AS "corpCode",
                   c.corp_name     AS "corpName",
                   cm.metric_code  AS "metricCode",
                   cm.fiscal_year  AS "fiscalYear",
                   cm.metric_value AS "value",
                   m.value_scale   AS "valueScale"
            FROM company c
            LEFT JOIN company_metric cm
                   ON cm.corp_code   = c.corp_code
                  AND cm.fiscal_year IN (:year, :prevYear)
                  AND cm.metric_code IN (:metricCodes)
            LEFT JOIN metric m ON m.metric_code = cm.metric_code
            WHERE c.corp_code IN (:corpCodes)
            ORDER BY c.corp_name, cm.metric_code, cm.fiscal_year
            """, nativeQuery = true)
    List<IndustryComparisonProjection> findValues(@Param("corpCodes") Collection<String> corpCodes,
                                                  @Param("metricCodes") Collection<String> metricCodes,
                                                  @Param("year") int year,
                                                  @Param("prevYear") int prevYear);

    /**
     * 같은 KSIC 중분류에 속한 기업 수. 응답의 {@code industry.companyCount} 다.
     *
     * <p>v1 에서는 비교군에 실린 기업 수와 같은 값이었다. v2 는 peers 만 실으므로 둘이 갈린다 —
     * 화면은 "이 산업에 기업이 몇 곳인데 그중 몇 곳을 골랐다"를 보여줘야 하므로 산업 전체 수다.
     */
    @Query(value = "SELECT count(*) FROM company WHERE industry_code = :division", nativeQuery = true)
    long countByIndustry(@Param("division") String division);
}

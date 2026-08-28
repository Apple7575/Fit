package com.ssafy.companyanalysis.comparison.repository;

import com.ssafy.companyanalysis.company.domain.Company;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;

public interface IndustryComparisonRepository extends Repository<Company, String> {

    /**
     * 같은 KSIC 중분류(division) 기업들의 지정 연도 지표값을 조회한다.
     *
     * <p>기업을 기준으로 지표값을 LEFT JOIN 하므로, 해당 연도에 값이 없는 기업도
     * 결과에서 빠지지 않는다(F-12·F-20). value_scale 은 응답 직렬화 자릿수를 맞추기 위해
     * metric 에서 함께 가져온다. 정렬은 corp_name 기준이며 대상 기업 우선 배치는 서비스가 한다.
     */
    @Query(value = """
            SELECT c.corp_code     AS "corpCode",
                   c.corp_name     AS "corpName",
                   cm.metric_code  AS "metricCode",
                   cm.metric_value AS "value",
                   m.value_scale   AS "valueScale"
            FROM company c
            LEFT JOIN company_metric cm
                   ON cm.corp_code   = c.corp_code
                  AND cm.fiscal_year = :year
                  AND cm.metric_code IN (:metricCodes)
            LEFT JOIN metric m ON m.metric_code = cm.metric_code
            WHERE c.industry_code = :division
            ORDER BY c.corp_name, cm.metric_code
            """, nativeQuery = true)
    List<IndustryComparisonProjection> findComparison(@Param("division") String division,
                                                      @Param("year") int year,
                                                      @Param("metricCodes") Collection<String> metricCodes);
}

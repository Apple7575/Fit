package com.ssafy.companyanalysis.focus.repository;

import com.ssafy.companyanalysis.company.domain.Company;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;

/**
 * 사업부문 매출·인력 증감 조회 전용 리포지토리.
 *
 * <p>기업 개요의 부문 조회({@code CompanyProfileRepository})와 같은 테이블을 읽지만 쿼리가
 * 다르다. 여기는 전년 행을 한 번 더 조인해 증감을 낼 재료를 가져온다. 개요는 증감을 쓰지
 * 않으므로 그 조인을 지고 갈 이유가 없다.
 */
public interface CompanySegmentChangeRepository extends Repository<Company, String> {

    /**
     * 이 기업의 부문 데이터가 있는 가장 최근 회계연도. 하나도 없으면 null 이다.
     *
     * <p>직원 수 지표의 연도까지 함께 본다. 응답의 {@code employeeTotalChange} 가 그 지표에서
     * 나오므로, 부문 테이블만 보고 정하면 부문 공시는 없고 전사 인원만 적재된 기업에서
     * 전사 증감이 조용히 사라진다.
     */
    @Query(value = """
            SELECT max(fiscal_year)
            FROM (SELECT fiscal_year FROM segment_metric WHERE corp_code = :corpCode
                  UNION ALL
                  SELECT fiscal_year FROM company_metric
                   WHERE corp_code = :corpCode AND metric_code IN (:metricCodes)) y
            """, nativeQuery = true)
    Integer findLatestFiscalYear(@Param("corpCode") String corpCode,
                                 @Param("metricCodes") Collection<String> metricCodes);

    /**
     * 지정 연도의 부문별 매출과 올해·전년 직원 수를 조회한다.
     *
     * <p>기준 연도 행을 왼쪽에 두고 전년을 LEFT JOIN 한다. 작년에 있었지만 올해 없는 부문은
     * 결과에서 빠진다 — 이 응답은 올해의 부문 구성을 보여주는 것이고, 사라진 부문을 인원
     * 전량 감소로 싣는 것은 사실과 다르다.
     *
     * <p>정렬은 매출이 큰 부문부터이고 미공시 부문은 뒤로 보낸다. 개요의 부문 조회와 같은
     * 규칙이라 두 화면에서 부문 순서가 어긋나지 않는다.
     *
     * <p>별칭을 큰따옴표로 감싼 것은 PostgreSQL 이 따옴표 없는 식별자를 소문자로 접어
     * 프로젝션의 getter 와 어긋나기 때문이다.
     */
    @Query(value = """
            WITH wide AS (
                SELECT fiscal_year,
                       segment_name,
                       max(metric_value) FILTER (WHERE metric_code = 'segment_revenue')
                           AS revenue,
                       max(metric_value) FILTER (WHERE metric_code = 'segment_employee_count')::integer
                           AS employee_count
                FROM segment_metric
                WHERE corp_code = :corpCode AND fiscal_year IN (:fiscalYear, :prevYear)
                GROUP BY fiscal_year, segment_name
            )
            SELECT cur.segment_name   AS "segmentCode",
                   cur.revenue        AS "revenue",
                   cur.employee_count AS "employeeCount",
                   prv.employee_count AS "prevEmployeeCount"
            FROM wide cur
            LEFT JOIN wide prv
                   ON prv.segment_name = cur.segment_name
                  AND prv.fiscal_year  = :prevYear
            WHERE cur.fiscal_year = :fiscalYear
            ORDER BY cur.revenue DESC NULLS LAST, cur.segment_name
            """, nativeQuery = true)
    List<SegmentChangeProjection> findSegmentChanges(@Param("corpCode") String corpCode,
                                                     @Param("fiscalYear") int fiscalYear,
                                                     @Param("prevYear") int prevYear);
}

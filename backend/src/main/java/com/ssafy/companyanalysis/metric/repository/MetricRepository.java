package com.ssafy.companyanalysis.metric.repository;

import com.ssafy.companyanalysis.metric.domain.Metric;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface MetricRepository extends JpaRepository<Metric, String> {

    /** 값이 하나도 없는 기업의 응답 골격을 만들 때 쓴다. */
    List<Metric> findByActiveTrueOrderByDisplayOrderAsc();

    /** 미지원 지표(400) 판별과, 값이 없을 때의 label/unit 조달을 겸한다. */
    Optional<Metric> findByMetricCodeAndActiveTrue(String metricCode);

    /**
     * 지정 연도의 지표 6종을 값·전년값과 함께 조회한다.
     *
     * <p>기준이 {@code metric} 카탈로그이고 값 테이블을 LEFT JOIN 하므로,
     * 적재된 값이 하나도 없어도 결과는 항상 활성 지표 수만큼 나온다.
     * (AC: 일부 값 누락 시 응답 구조는 유지된다)
     *
     * <p>전년 값은 저장하지 않고 같은 테이블의 {@code fiscal_year - 1} 행을
     * 한 번 더 조인해 조회 시점에 만든다. 값을 저장하면 재적재 때 원본과 어긋난다.
     *
     * <p>별칭을 큰따옴표로 감싼 것은 PostgreSQL 이 따옴표 없는 식별자를 소문자로 접어
     * 프로젝션의 getter 와 어긋나기 때문이다.
     */
    @Query(value = """
            SELECT m.metric_code AS "metricCode",
                   m.name_ko     AS "label",
                   m.unit        AS "unit",
                   m.value_scale AS "valueScale",
                   cur.metric_value AS "value",
                   prv.metric_value AS "prevValue"
            FROM metric m
            LEFT JOIN company_metric cur
                   ON cur.metric_code = m.metric_code
                  AND cur.corp_code   = :corpCode
                  AND cur.fiscal_year = :year
            LEFT JOIN company_metric prv
                   ON prv.metric_code = m.metric_code
                  AND prv.corp_code   = :corpCode
                  AND prv.fiscal_year = :prevYear
            WHERE m.is_active
            ORDER BY m.display_order
            """, nativeQuery = true)
    List<MetricValueProjection> findMetricValues(@Param("corpCode") String corpCode,
                                                 @Param("year") int year,
                                                 @Param("prevYear") int prevYear);

    /** 위 쿼리에서 지표 하나만 잘라낸 것. 통합 조회와 같은 값이 나와야 한다. */
    @Query(value = """
            SELECT m.metric_code AS "metricCode",
                   m.name_ko     AS "label",
                   m.unit        AS "unit",
                   m.value_scale AS "valueScale",
                   cur.metric_value AS "value",
                   prv.metric_value AS "prevValue"
            FROM metric m
            LEFT JOIN company_metric cur
                   ON cur.metric_code = m.metric_code
                  AND cur.corp_code   = :corpCode
                  AND cur.fiscal_year = :year
            LEFT JOIN company_metric prv
                   ON prv.metric_code = m.metric_code
                  AND prv.corp_code   = :corpCode
                  AND prv.fiscal_year = :prevYear
            WHERE m.is_active
              AND m.metric_code = :metricCode
            """, nativeQuery = true)
    Optional<MetricValueProjection> findMetricValue(@Param("corpCode") String corpCode,
                                                    @Param("metricCode") String metricCode,
                                                    @Param("year") int year,
                                                    @Param("prevYear") int prevYear);

    /**
     * year 를 주지 않았을 때 쓸 기준연도. 값이 하나도 없으면 비어 있다.
     *
     * <p>지표별이 아니라 기업 단위 최신연도다. 통합 조회와 개별 조회가
     * 같은 연도를 보게 하려면 기준이 하나여야 한다.
     */
    @Query(value = "SELECT max(fiscal_year) FROM company_metric WHERE corp_code = :corpCode",
            nativeQuery = true)
    Integer findLatestFiscalYear(@Param("corpCode") String corpCode);

    /**
     * 지정 구간의 지표별 연도값을 조회한다(F-14).
     *
     * <p>값이 있는 연도만 행으로 나온다. 구간 전체를 채운 격자는 서비스가 만든다 —
     * 빠진 연도를 SQL 로 채우려면 generate_series 가 필요한데, 그러면 자릿수 처리와
     * 격자 채우기가 SQL 과 자바로 흩어져 검증이 어려워진다.
     *
     * <p>정렬은 {@code company_metric_timeseries_idx}(corp_code, metric_code, fiscal_year)
     * 가 그대로 받아준다.
     */
    @Query(value = """
            SELECT m.metric_code    AS "metricCode",
                   m.name_ko        AS "label",
                   m.unit           AS "unit",
                   m.value_scale    AS "valueScale",
                   cm.fiscal_year   AS "fiscalYear",
                   cm.metric_value  AS "value"
            FROM metric m
            LEFT JOIN company_metric cm
                   ON cm.metric_code = m.metric_code
                  AND cm.corp_code   = :corpCode
                  AND cm.fiscal_year BETWEEN :fromYear AND :toYear
            WHERE m.is_active
              AND m.metric_code IN (:metricCodes)
            ORDER BY m.display_order, cm.fiscal_year
            """, nativeQuery = true)
    List<MetricPointProjection> findMetricPoints(@Param("corpCode") String corpCode,
                                                 @Param("metricCodes") Collection<String> metricCodes,
                                                 @Param("fromYear") int fromYear,
                                                 @Param("toYear") int toYear);
}

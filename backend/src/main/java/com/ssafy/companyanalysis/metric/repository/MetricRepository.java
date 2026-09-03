package com.ssafy.companyanalysis.metric.repository;

import com.ssafy.companyanalysis.metric.domain.Metric;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;

public interface MetricRepository extends JpaRepository<Metric, String> {

    /** {@code keys} 검증에 쓸 지원 목록. 기본 6종은 이 안에서 {@code isCore} 로 다시 거른다. */
    List<Metric> findByActiveTrueOrderByDisplayOrderAsc();

    /**
     * 지정 연도의 지표 값을 전년값과 함께 조회한다.
     *
     * <p>기준이 {@code metric} 카탈로그이고 값 테이블을 LEFT JOIN 하므로,
     * 적재된 값이 하나도 없어도 결과는 항상 요청한 지표 수만큼 나온다.
     * (AC: 일부 값 누락 시 응답 구조는 유지된다)
     *
     * <p>{@code is_active} 로 거르지 않고 {@code metricCodes} 로만 좁힌다. 이 목록은
     * 서비스가 카탈로그에서 만들어 넘기므로(기본이면 core, 아니면 검증을 통과한 keys)
     * 여기서 한 번 더 거를 필요가 없다.
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
            WHERE m.metric_code IN (:metricCodes)
            ORDER BY m.display_order
            """, nativeQuery = true)
    List<MetricValueProjection> findMetricValues(@Param("corpCode") String corpCode,
                                                 @Param("metricCodes") Collection<String> metricCodes,
                                                 @Param("year") int year,
                                                 @Param("prevYear") int prevYear);

    /**
     * 수익성·안정성 비율의 원본 값을 읽는다.
     *
     * <p>카탈로그를 거치지 않고 {@code company_metric} 을 직접 읽는 이유는, 부채총계·자본총계가
     * {@code is_active = false} 인 내부 지표라서다(V7). 화면에 내보낼 지표가 아니라 비율 계산의
     * 입력이므로 다른 조회에는 걸리지 않아야 하고, 여기서만 이름을 대고 꺼내 온다.
     *
     * <p>값이 없는 계정은 행 자체가 나오지 않는다. 없는 것과 0 인 것을 가르는 일은 서비스가 한다.
     */
    @Query(value = """
            SELECT cm.metric_code   AS "metricCode",
                   cm.metric_value  AS "value"
            FROM company_metric cm
            WHERE cm.corp_code   = :corpCode
              AND cm.fiscal_year = :year
              AND cm.metric_code IN (:metricCodes)
            """, nativeQuery = true)
    List<MetricAmountProjection> findRawValues(@Param("corpCode") String corpCode,
                                               @Param("metricCodes") Collection<String> metricCodes,
                                               @Param("year") int year);

    /**
     * year 를 주지 않았을 때 쓸 기준연도. 값이 하나도 없으면 비어 있다.
     *
     * <p>지표별이 아니라 기업 단위 최신연도다. 지표마다 기준연도가 달라지면
     * 한 화면 안에서 서로 다른 해의 값이 섞인다.
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
     * <p>호출자는 응답 구간보다 한 해 앞선 {@code fromYear} 를 넘긴다. 구간 첫 해의
     * {@code changeRate} 를 내려면 그 전년 값이 있어야 하기 때문이다. 여분의 해는
     * 서비스가 격자를 만들 때 버린다.
     *
     * <p>{@code is_active} 로 거르지 않는 것은 {@code findMetricValues} 와 같은 이유다.
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
            WHERE m.metric_code IN (:metricCodes)
            ORDER BY m.display_order, cm.fiscal_year
            """, nativeQuery = true)
    List<MetricPointProjection> findMetricPoints(@Param("corpCode") String corpCode,
                                                 @Param("metricCodes") Collection<String> metricCodes,
                                                 @Param("fromYear") int fromYear,
                                                 @Param("toYear") int toYear);
}

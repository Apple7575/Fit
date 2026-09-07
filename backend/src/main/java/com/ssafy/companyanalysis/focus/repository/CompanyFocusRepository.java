package com.ssafy.companyanalysis.focus.repository;

import com.ssafy.companyanalysis.company.domain.Company;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

/**
 * 집중 분야의 사업 방향·R&D 조회 전용 리포지토리.
 *
 * <p>세 테이블에 엔티티를 만들지 않았다. 조회만 하고 쓰기는 파이프라인이 한다.
 * {@link Repository} 를 상속해 저장·삭제 메서드를 노출하지 않는다.
 */
public interface CompanyFocusRepository extends Repository<Company, String> {

    /**
     * 이 기업의 집중 분야 데이터가 있는 가장 최근 회계연도. 하나도 없으면 null 이다.
     *
     * <p>사업 방향과 R&D 분야뿐 아니라 R&D 지표의 연도까지 함께 본다. 응답의 두 블록이
     * 출처가 달라서, 한쪽만 보고 기준연도를 정하면 다른 쪽이 조용히 빈다. 사업 방향 분석이
     * 아직 안 돌았는데 R&D 비용은 적재된 기업이 실제로 그런 경우다.
     *
     * <p>사업 방향 목록 테이블은 보지 않는다. 그 테이블이 본 행을 복합 FK 로 참조하므로
     * 목록이 있으면 본 행도 반드시 있다.
     *
     * <p>{@code metricCodes} 를 파라미터로 받는 것은 지표 코드를 쿼리에 박지 않기 위해서다.
     * 서비스가 쓰는 상수와 갈리면 기준연도와 실제 조회가 서로 다른 지표를 보게 된다.
     */
    @Query(value = """
            SELECT max(fiscal_year)
            FROM (SELECT fiscal_year FROM company_focus_direction WHERE corp_code = :corpCode
                  UNION ALL
                  SELECT fiscal_year FROM company_rnd_field       WHERE corp_code = :corpCode
                  UNION ALL
                  SELECT fiscal_year FROM company_metric
                   WHERE corp_code = :corpCode AND metric_code IN (:metricCodes)) y
            """, nativeQuery = true)
    Integer findLatestFiscalYear(@Param("corpCode") String corpCode,
                                 @Param("metricCodes") Collection<String> metricCodes);

    /**
     * 사업 방향 본 행. 분석이 돌지 않은 기업·연도는 비어 있다.
     *
     * <p>별칭을 큰따옴표로 감싼 것은 PostgreSQL 이 따옴표 없는 식별자를 소문자로 접어
     * 프로젝션의 getter 와 어긋나기 때문이다.
     */
    @Query(value = """
            SELECT strategy_change AS "strategyChange"
            FROM company_focus_direction
            WHERE corp_code = :corpCode AND fiscal_year = :fiscalYear
            """, nativeQuery = true)
    Optional<FocusDirectionProjection> findDirection(@Param("corpCode") String corpCode,
                                                     @Param("fiscalYear") int fiscalYear);

    /**
     * 신규사업·키워드 목록을 한 번에 읽는다. 서비스가 {@code itemType} 으로 나눈다.
     *
     * <p>정렬은 AI 가 낸 순서다. 같은 순서 값이 겹쳐 실행마다 결과가 달라지지 않도록
     * 이름을 마지막 정렬 키로 둔다.
     */
    @Query(value = """
            SELECT item_type AS "itemType",
                   item_name AS "itemName"
            FROM company_focus_direction_item
            WHERE corp_code = :corpCode AND fiscal_year = :fiscalYear
            ORDER BY item_type, display_order, item_name
            """, nativeQuery = true)
    List<FocusDirectionItemProjection> findDirectionItems(@Param("corpCode") String corpCode,
                                                          @Param("fiscalYear") int fiscalYear);

    /** R&D 중점 분야. 사업보고서 기재 순서로 정렬한다. */
    @Query(value = """
            SELECT field_name
            FROM company_rnd_field
            WHERE corp_code = :corpCode AND fiscal_year = :fiscalYear
            ORDER BY display_order, field_name
            """, nativeQuery = true)
    List<String> findRndFields(@Param("corpCode") String corpCode,
                               @Param("fiscalYear") int fiscalYear);
}

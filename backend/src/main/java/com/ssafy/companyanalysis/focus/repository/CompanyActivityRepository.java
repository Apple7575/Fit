package com.ssafy.companyanalysis.focus.repository;

import com.ssafy.companyanalysis.company.domain.Company;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

import java.util.List;

/** 투자·M&A 이벤트 조회 전용 리포지토리. */
public interface CompanyActivityRepository extends Repository<Company, String> {

    /**
     * 한 기업의 특정 유형 이벤트를 최신 연도부터 조회한다.
     *
     * <p>from/to 는 선택이라 null 이 올 수 있다. 값이 없으면 그 방향으로는 제한하지 않는다.
     * 조건을 SQL 안에서 끄는 방식을 쓴 것은 쿼리를 네 개로 늘리지 않기 위해서다.
     *
     * <p>{@code cast} 가 붙은 것은 PostgreSQL 때문이다. 네이티브 쿼리의 파라미터에 null 이
     * 들어가면 타입을 못 정해 {@code could not determine data type} 으로 실패한다.
     *
     * <p>정렬은 최신 연도부터, 같은 해에서는 금액이 큰 순이다. 금액을 공시하지 않은 건은
     * 그 해의 뒤로 가고, 마지막으로 적재 순서를 써서 실행마다 순서가 흔들리지 않게 한다.
     * 화면은 네 유형을 한 타임라인에 섞어 다시 정렬하지만, 같은 해 같은 유형의 순서는
     * 서버가 정한 그대로 남는다.
     *
     * <p>별칭을 큰따옴표로 감싼 것은 PostgreSQL 이 따옴표 없는 식별자를 소문자로 접어
     * 프로젝션의 getter 와 어긋나기 때문이다.
     */
    @Query(value = """
            SELECT fiscal_year   AS "year",
                   activity_type AS "type",
                   field_name    AS "field",
                   purpose       AS "purpose",
                   amount        AS "amount"
            FROM company_activity
            WHERE corp_code     = :corpCode
              AND activity_type = :activityType
              AND (cast(:fromYear AS integer) IS NULL OR fiscal_year >= :fromYear)
              AND (cast(:toYear   AS integer) IS NULL OR fiscal_year <= :toYear)
            ORDER BY fiscal_year DESC, amount DESC NULLS LAST, id
            """, nativeQuery = true)
    List<ActivityProjection> findActivities(@Param("corpCode") String corpCode,
                                            @Param("activityType") String activityType,
                                            @Param("fromYear") Integer fromYear,
                                            @Param("toYear") Integer toYear);
}

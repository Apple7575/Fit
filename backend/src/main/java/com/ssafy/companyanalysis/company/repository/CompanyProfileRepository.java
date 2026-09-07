package com.ssafy.companyanalysis.company.repository;

import com.ssafy.companyanalysis.company.domain.Company;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

import java.util.List;

/**
 * 기업 개요(사업·사업부문·제품) 조회 전용 리포지토리.
 *
 * <p>세 테이블에 엔티티를 만들지 않았다. 조회만 하고 쓰기는 파이썬 파이프라인이 하므로
 * 매핑을 유지할 이유가 없다. {@code company_metric} 도 같은 이유로 엔티티가 없다.
 *
 * <p>{@link Repository} 를 상속하는 것은 저장·삭제 메서드를 노출하지 않기 위해서다.
 * 산업 비교 후보 목록 리포지토리와 같은 방식이다.
 */
public interface CompanyProfileRepository extends Repository<Company, String> {

    /**
     * 이 기업의 개요가 적재된 가장 최근 회계연도. 하나도 없으면 null 이다.
     *
     * <p>세 테이블을 모두 보는 이유는 셋의 적재 시점이 다를 수 있기 때문이다. 사업 목록만
     * 먼저 들어오고 부문 매출은 다음 배치에서 들어오는 식이면, 한 테이블만 봤을 때 이미
     * 들어와 있는 해를 놓친다.
     *
     * <p>{@code company_metric} 의 최신 연도(기업 헤더의 dataYear)를 쓰지 않는다. 재무
     * 지표가 2025년까지 들어와 있어도 사업보고서 추출이 2024년까지면, 그 해를 기준으로
     * 조회한 개요는 전부 빈 값이 된다. 실제로 있는 데이터를 없는 것처럼 보여주는 셈이다.
     * 그래서 개요의 기준연도는 개요 데이터에서 정하고, 어느 해인지를 응답의 year 로
     * 알려 준다 — 명세가 이 응답에 year 를 둔 이유이기도 하다.
     *
     * <p>세 테이블 모두 PK 선두가 (corp_code, fiscal_year) 라 max 는 인덱스로 끝난다.
     */
    @Query(value = """
            SELECT max(fiscal_year)
            FROM (SELECT fiscal_year FROM company_business WHERE corp_code = :corpCode
                  UNION ALL
                  SELECT fiscal_year FROM company_segment  WHERE corp_code = :corpCode
                  UNION ALL
                  SELECT fiscal_year FROM company_product  WHERE corp_code = :corpCode) y
            """, nativeQuery = true)
    Integer findLatestFiscalYear(@Param("corpCode") String corpCode);

    /**
     * 주요 사업 목록. 사업보고서 기재 순서로 정렬한다.
     *
     * <p>기재 순서가 같은 행이 섞이지 않게 이름을 두 번째 정렬 키로 둔다. display_order 는
     * 추출 결과라 중복이 들어올 수 있고, 그때 순서가 실행마다 달라지면 화면이 흔들린다.
     */
    @Query(value = """
            SELECT business_name
            FROM company_business
            WHERE corp_code = :corpCode AND fiscal_year = :fiscalYear
            ORDER BY display_order, business_name
            """, nativeQuery = true)
    List<String> findBusinessNames(@Param("corpCode") String corpCode,
                                   @Param("fiscalYear") int fiscalYear);

    /** 주요 제품 목록. 정렬 규칙은 주요 사업과 같다. */
    @Query(value = """
            SELECT product_name
            FROM company_product
            WHERE corp_code = :corpCode AND fiscal_year = :fiscalYear
            ORDER BY display_order, product_name
            """, nativeQuery = true)
    List<String> findProductNames(@Param("corpCode") String corpCode,
                                  @Param("fiscalYear") int fiscalYear);

    /**
     * 사업부문별 매출. 매출이 큰 부문부터, 미공시 부문은 뒤로 보낸다.
     *
     * <p>부문에는 기재 순서를 두지 않았다. 사업·제품과 달리 정렬 기준이 데이터 안에 있고,
     * 화면이 비중 막대를 그리므로 큰 부문이 위에 오는 편이 읽기 쉽다. 미공시 부문을
     * {@code NULLS LAST} 로 내리는 것도 같은 이유다 — 값이 없는 부문이 목록 맨 위에서
     * 자리를 차지하면 주력 부문이 밀린다.
     *
     * <p>별칭을 큰따옴표로 감싼 것은 PostgreSQL 이 따옴표 없는 식별자를 소문자로 접어
     * 프로젝션의 getter 와 어긋나기 때문이다.
     */
    @Query(value = """
            SELECT segment_code AS "segmentCode",
                   revenue      AS "revenue"
            FROM company_segment
            WHERE corp_code = :corpCode AND fiscal_year = :fiscalYear
            ORDER BY revenue DESC NULLS LAST, segment_code
            """, nativeQuery = true)
    List<ProfileSegmentProjection> findSegments(@Param("corpCode") String corpCode,
                                                @Param("fiscalYear") int fiscalYear);
}

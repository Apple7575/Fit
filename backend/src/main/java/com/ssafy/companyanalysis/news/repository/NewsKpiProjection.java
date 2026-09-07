package com.ssafy.companyanalysis.news.repository;

/**
 * 이슈 KPI 세 건을 한 번에 담는 프로젝션.
 *
 * <p>쿼리를 셋으로 나누지 않은 이유는 세 값이 모두 같은 기업·같은 기간의 같은 테이블을
 * 훑기 때문이다. 조건부 집계로 한 번에 세면 스캔이 한 번으로 끝난다.
 *
 * <p>세 값 모두 0 이 될 수 있고 그것은 "그 기간에 그런 이슈가 없었다"는 사실이다.
 * 값을 못 구하는 경우(분석이 아직 안 돌아 중요도가 전부 null)와는 서비스가 가른다.
 */
public interface NewsKpiProjection {

    /** 기간 내 중요도가 기준 이상인 뉴스 수. */
    long getImportantCount();

    /** 그중 투자 카테고리 수. */
    long getInvestmentCount();

    /** 그중 기술 카테고리 수. */
    long getTechCount();

    /**
     * 기간 내 중요도가 매겨진 뉴스가 하나라도 있었나. 전부 없으면 위 셋은 뜻이 없다.
     *
     * <p>{@code Boolean} 인 것은 기간에 뉴스가 아예 없을 때 집계가 null 을 주기 때문이다.
     * 원시 타입으로 받으면 그 경우에 언박싱이 터진다.
     */
    Boolean getScored();
}

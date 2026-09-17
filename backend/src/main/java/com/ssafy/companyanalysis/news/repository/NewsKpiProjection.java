package com.ssafy.companyanalysis.news.repository;

/**
 * 이슈 KPI 를 담는 프로젝션.
 *
 * <p>두 값을 한 쿼리로 세는 것은 같은 기업·같은 기간의 같은 테이블을 훑기 때문이다.
 * 조건부 집계로 한 번에 세면 스캔이 한 번으로 끝난다.
 *
 * <p>V16 에서 투자·기술 건수가 빠졌다. 카테고리 컬럼이 없어져 셀 근거가 사라졌다.
 */
public interface NewsKpiProjection {

    /** 기간 내 중요도가 기준 이상인 뉴스 수. 0 이면 "그런 이슈가 없었다"는 사실이다. */
    long getImportantCount();

    /**
     * 기간 내 중요도가 매겨진 뉴스가 하나라도 있었나. 전부 없으면 위 값은 뜻이 없다.
     *
     * <p>{@code Boolean} 인 것은 기간에 뉴스가 아예 없을 때 집계가 null 을 주기 때문이다.
     * 원시 타입으로 받으면 그 경우에 언박싱이 터진다.
     */
    Boolean getScored();
}

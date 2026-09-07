package com.ssafy.companyanalysis.focus.repository;

/**
 * 사업 방향 본 행의 프로젝션. 목록 두 종은 별도 테이블이라 여기 없다.
 *
 * <p>행이 있는데 {@code strategyChange} 만 null 인 경우와 행 자체가 없는 경우를 가르기 위해
 * 조회는 {@code Optional} 을 돌려준다. 앞은 분석은 돌았지만 전략 변화를 못 뽑은 것이고,
 * 뒤는 분석이 아예 없는 것이다. 응답에서는 둘 다 null 이지만 재분석 대상인지가 다르다.
 */
public interface FocusDirectionProjection {

    String getStrategyChange();
}

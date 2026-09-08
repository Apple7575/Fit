package com.ssafy.companyanalysis.news.repository;

import java.math.BigDecimal;

/**
 * 상위 뉴스 한 건. 순위는 여기 없다 — 쿼리가 정렬해 주고 서비스가 1부터 매긴다.
 *
 * <p>순위를 SQL 의 윈도 함수로 만들 수도 있지만, 그러면 limit 이 순위 계산 뒤에 걸리는지
 * 앞에 걸리는지가 쿼리를 읽는 사람마다 달리 보인다. 정렬만 SQL 에 두고 번호는 자바에서 센다.
 */
public interface TopNewsProjection {

    long getId();

    String getTitle();

    BigDecimal getImportanceScore();
}

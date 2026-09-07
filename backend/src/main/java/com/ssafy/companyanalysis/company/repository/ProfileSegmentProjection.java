package com.ssafy.companyanalysis.company.repository;

import java.math.BigDecimal;

/**
 * 사업부문별 매출 조회의 네이티브 쿼리 결과 매핑용 인터페이스 프로젝션.
 *
 * <p>비중({@code revenueShare})과 합계({@code totalRevenue})는 여기 없다. 둘 다 부문
 * 매출에서 계산하는 파생값이라 서비스가 만든다. 쿼리에서 윈도 함수로 비중까지 뽑을 수도
 * 있지만, 합계를 두 번(쿼리와 서비스) 정의하게 되어 규칙이 갈릴 자리가 생긴다.
 */
public interface ProfileSegmentProjection {

    String getSegmentCode();

    /** 부문 매출(원). 미공시 부문은 null 이며 0 과 다른 사실이다. */
    BigDecimal getRevenue();
}

package com.ssafy.companyanalysis.focus.repository;

import java.math.BigDecimal;

/**
 * 사업부문 한 곳의 매출과 올해·전년 직원 수.
 *
 * <p>증감({@code employeeChange})과 비중({@code revenueShare})은 여기 없다. 둘 다 파생값이라
 * 서비스가 만든다. 전년 인원을 그대로 싣는 것은 기업 개요의 부문 조회와 달리 이 응답이
 * 증감을 내보내기 때문이다.
 */
public interface SegmentChangeProjection {

    String getSegmentCode();

    /** 부문 매출(원). 미공시는 null. */
    BigDecimal getRevenue();

    /** 올해 부문 직원 수(명). 미공시는 null. */
    Integer getEmployeeCount();

    /** 전년 부문 직원 수(명). 전년 행이 없거나 미공시면 null. */
    Integer getPrevEmployeeCount();
}

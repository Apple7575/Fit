package com.ssafy.companyanalysis.focus.repository;

import java.math.BigDecimal;

/** 투자·M&A 이벤트 한 건. 응답 항목과 1:1 이라 파생값이 없다. */
public interface ActivityProjection {

    Integer getYear();

    String getType();

    String getField();

    String getPurpose();

    BigDecimal getAmount();
}

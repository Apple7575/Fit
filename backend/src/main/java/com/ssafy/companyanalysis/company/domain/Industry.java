package com.ssafy.companyanalysis.company.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** 표준산업분류. 동일 산업 비교(US-04)의 기준 축. */
@Entity
@Table(name = "industry")
public class Industry {

    @Id
    @Column(name = "industry_code", length = 10)
    private String industryCode;

    @Column(name = "industry_name", length = 200, nullable = false)
    private String industryName;

    protected Industry() {
    }

    public String getIndustryCode() {
        return industryCode;
    }

    public String getIndustryName() {
        return industryName;
    }
}

package com.ssafy.companyanalysis.company.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

import java.time.LocalDate;
import java.time.OffsetDateTime;

/**
 * 기업 마스터. 모든 조회 API 의 진입점이며 식별자는 DART 고유번호 8자리다.
 *
 * <p>스키마는 Flyway 가 만들고 여기서는 매핑만 한다. ddl-auto=validate 이므로
 * 컬럼이 어긋나면 기동 시점에 걸린다.
 */
@Entity
@Table(name = "company")
public class Company {

    @Id
    @Column(name = "corp_code", length = 8)
    private String corpCode;

    @Column(name = "corp_name", length = 200, nullable = false)
    private String corpName;

    @Column(name = "corp_name_eng", length = 200)
    private String corpNameEng;

    @Column(name = "stock_code", length = 6)
    private String stockCode;

    @Column(name = "corp_cls", length = 1)
    private String corpCls;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "industry_code")
    private Industry industry;

    @Column(name = "ceo_nm", length = 100)
    private String ceoNm;

    @Column(name = "established_date")
    private LocalDate establishedDate;

    @Column(name = "listed_date")
    private LocalDate listedDate;

    @Column(name = "dart_modify_date", length = 8)
    private String dartModifyDate;

    @Column(name = "created_at", nullable = false, insertable = false, updatable = false)
    private OffsetDateTime createdAt;

    @Column(name = "updated_at", nullable = false, insertable = false, updatable = false)
    private OffsetDateTime updatedAt;

    protected Company() {
    }

    public String getCorpCode() {
        return corpCode;
    }

    public String getCorpName() {
        return corpName;
    }

    public String getStockCode() {
        return stockCode;
    }

    public Industry getIndustry() {
        return industry;
    }
}

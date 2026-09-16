package com.ssafy.companyanalysis.agent.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.Immutable;

/**
 * AI 서비스가 만들어 둔 채용공고 분석. 읽기 전용이다.
 *
 * <p>{@code ai_job_contexts} 는 FastAPI 가 psycopg 로 직접 읽고 쓴다(DDL 만 Flyway).
 * 백엔드는 방에 붙은 공고 본문을 꺼내 쓰기만 하므로 필요한 칸만 매핑한다.
 */
@Entity
@Immutable
@Table(name = "ai_job_contexts")
public class JobContext {

    @Id
    @Column(name = "context_id", length = 80)
    private String contextId;

    @Column(name = "company_name", length = 100, nullable = false)
    private String companyName;

    @Column(name = "position_name", length = 200, nullable = false)
    private String positionName;

    @Column(name = "jd_text", nullable = false)
    private String jdText;

    protected JobContext() {
    }

    public String getContextId() {
        return contextId;
    }

    public String getCompanyName() {
        return companyName;
    }

    public String getPositionName() {
        return positionName;
    }

    public String getJdText() {
        return jdText;
    }
}

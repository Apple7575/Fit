package com.ssafy.companyanalysis.coverletter.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.OffsetDateTime;

/** 자기소개서. 문항/코멘트는 연관관계 대신 FK 로 분리해 저장 시 전체 교체한다. */
@Entity
@Table(name = "cover_letter")
public class CoverLetter {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false, updatable = false)
    private Long userId;

    @Column(name = "title", length = 120, nullable = false)
    private String title;

    @Column(name = "target_company", length = 120)
    private String targetCompany;

    @Column(name = "target_position", length = 120)
    private String targetPosition;

    /**
     * 이 자소서를 내는 공고의 분석 식별자({@code ai_job_contexts.context_id}). 공고를 넣지 않았으면 null.
     *
     * <p>검토 방을 깔 때 여기서 꺼내 방에 붙인다. 방마다 따로 등록하면 같은 공고를 자소서 하나에
     * 여섯 번 분석하게 된다.
     */
    @Column(name = "context_id", length = 80)
    private String contextId;

    @Column(name = "updated_at", nullable = false)
    private OffsetDateTime updatedAt;

    protected CoverLetter() {
    }

    private CoverLetter(Long userId, String title, String targetCompany, String targetPosition,
                        String contextId) {
        this.userId = userId;
        this.title = title;
        this.targetCompany = targetCompany;
        this.targetPosition = targetPosition;
        this.contextId = contextId;
        this.updatedAt = OffsetDateTime.now();
    }

    public static CoverLetter create(Long userId, String title, String targetCompany,
                                     String targetPosition, String contextId) {
        return new CoverLetter(userId, title, targetCompany, targetPosition, contextId);
    }

    /**
     * 공고를 뺀 채로 저장하면 붙어 있던 공고도 떨어진다. 자소서를 고쳐 다른 공고에 내는 일이
     * 있으므로, 안 보냈다는 것과 지웠다는 것을 가르지 않는다.
     */
    public void update(String title, String targetCompany, String targetPosition, String contextId) {
        this.title = title;
        this.targetCompany = targetCompany;
        this.targetPosition = targetPosition;
        this.contextId = contextId;
        this.updatedAt = OffsetDateTime.now();
    }

    public Long getId() {
        return id;
    }

    public Long getUserId() {
        return userId;
    }

    public String getTitle() {
        return title;
    }

    public String getTargetCompany() {
        return targetCompany;
    }

    public String getTargetPosition() {
        return targetPosition;
    }

    public String getContextId() {
        return contextId;
    }

    public OffsetDateTime getUpdatedAt() {
        return updatedAt;
    }
}

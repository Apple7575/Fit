package com.ssafy.companyanalysis.interview.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.OffsetDateTime;

/** 모의 면접. 문항/피드백은 연관관계 대신 FK 로 분리해 저장 시 전체 교체한다. */
@Entity
@Table(name = "interview_session")
public class InterviewSession {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false, updatable = false)
    private Long userId;

    @Column(name = "target_company", length = 120)
    private String targetCompany;

    @Column(name = "target_position", length = 120)
    private String targetPosition;

    @Column(name = "interview_type", length = 20, nullable = false)
    private String interviewType;

    @Column(name = "cover_letter_id")
    private Long coverLetterId;

    @Column(name = "overall_summary")
    private String overallSummary;

    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    protected InterviewSession() {
    }

    private InterviewSession(Long userId, String targetCompany, String targetPosition, String interviewType,
                            Long coverLetterId, String overallSummary) {
        this.userId = userId;
        this.targetCompany = targetCompany;
        this.targetPosition = targetPosition;
        this.interviewType = interviewType;
        this.coverLetterId = coverLetterId;
        this.overallSummary = overallSummary;
        this.createdAt = OffsetDateTime.now();
    }

    public static InterviewSession create(Long userId, String targetCompany, String targetPosition,
                                          String interviewType, Long coverLetterId, String overallSummary) {
        return new InterviewSession(userId, targetCompany, targetPosition, interviewType, coverLetterId, overallSummary);
    }

    public Long getId() {
        return id;
    }

    public Long getUserId() {
        return userId;
    }

    public String getTargetCompany() {
        return targetCompany;
    }

    public String getTargetPosition() {
        return targetPosition;
    }

    public String getInterviewType() {
        return interviewType;
    }

    public Long getCoverLetterId() {
        return coverLetterId;
    }

    public String getOverallSummary() {
        return overallSummary;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }
}

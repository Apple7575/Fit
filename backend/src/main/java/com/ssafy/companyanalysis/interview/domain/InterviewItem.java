package com.ssafy.companyanalysis.interview.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** 면접 문항. 피드백 요약은 여기에, 세부 포인트는 interview_feedback_point 에 둔다. */
@Entity
@Table(name = "interview_item")
public class InterviewItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "session_id", nullable = false, updatable = false)
    private Long sessionId;

    @Column(name = "seq", nullable = false)
    private int seq;

    @Column(name = "question", nullable = false)
    private String question;

    @Column(name = "source_type", length = 20, nullable = false)
    private String sourceType;

    @Column(name = "transcript", nullable = false)
    private String transcript;

    @Column(name = "feedback_summary")
    private String feedbackSummary;

    protected InterviewItem() {
    }

    private InterviewItem(Long sessionId, int seq, String question, String sourceType, String transcript) {
        this.sessionId = sessionId;
        this.seq = seq;
        this.question = question;
        this.sourceType = sourceType;
        this.transcript = transcript;
    }

    public static InterviewItem create(Long sessionId, int seq, String question, String sourceType,
                                       String transcript) {
        return new InterviewItem(sessionId, seq, question, sourceType, transcript);
    }

    public void attachFeedback(String summary) {
        this.feedbackSummary = summary;
    }

    public Long getId() {
        return id;
    }

    public Long getSessionId() {
        return sessionId;
    }

    public int getSeq() {
        return seq;
    }

    public String getQuestion() {
        return question;
    }

    public String getSourceType() {
        return sourceType;
    }

    public String getTranscript() {
        return transcript;
    }

    public String getFeedbackSummary() {
        return feedbackSummary;
    }
}

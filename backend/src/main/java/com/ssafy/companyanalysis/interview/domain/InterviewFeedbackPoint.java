package com.ssafy.companyanalysis.interview.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** 문항 답변에 대한 강점(STRENGTH)/개선(IMPROVEMENT) 피드백 포인트. */
@Entity
@Table(name = "interview_feedback_point")
public class InterviewFeedbackPoint {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "item_id", nullable = false, updatable = false)
    private Long itemId;

    @Column(name = "seq", nullable = false)
    private int seq;

    @Column(name = "kind", length = 12, nullable = false)
    private String kind;

    @Column(name = "category", length = 20, nullable = false)
    private String category;

    @Column(name = "message", nullable = false)
    private String message;

    @Column(name = "suggestion")
    private String suggestion;

    protected InterviewFeedbackPoint() {
    }

    private InterviewFeedbackPoint(Long itemId, int seq, String kind, String category, String message,
                                   String suggestion) {
        this.itemId = itemId;
        this.seq = seq;
        this.kind = kind;
        this.category = category;
        this.message = message;
        this.suggestion = suggestion;
    }

    public static InterviewFeedbackPoint create(Long itemId, int seq, String kind, String category, String message,
                                                String suggestion) {
        return new InterviewFeedbackPoint(itemId, seq, kind, category, message, suggestion);
    }

    public Long getId() {
        return id;
    }

    public Long getItemId() {
        return itemId;
    }

    public int getSeq() {
        return seq;
    }

    public String getKind() {
        return kind;
    }

    public String getCategory() {
        return category;
    }

    public String getMessage() {
        return message;
    }

    public String getSuggestion() {
        return suggestion;
    }
}

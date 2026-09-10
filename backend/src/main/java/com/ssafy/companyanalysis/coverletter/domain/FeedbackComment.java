package com.ssafy.companyanalysis.coverletter.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** 문항 답변 구간별 코멘트. offset 이 없으면 프론트가 quote 로 위치를 찾는다. */
@Entity
@Table(name = "feedback_comment")
public class FeedbackComment {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "item_id", nullable = false, updatable = false)
    private Long itemId;

    @Column(name = "seq", nullable = false)
    private int seq;

    @Column(name = "quote", nullable = false)
    private String quote;

    @Column(name = "start_offset")
    private Integer startOffset;

    @Column(name = "end_offset")
    private Integer endOffset;

    @Column(name = "category", length = 20, nullable = false)
    private String category;

    @Column(name = "severity", length = 12, nullable = false)
    private String severity;

    @Column(name = "message", nullable = false)
    private String message;

    @Column(name = "suggestion")
    private String suggestion;

    protected FeedbackComment() {
    }

    private FeedbackComment(Long itemId, int seq, String quote, Integer startOffset, Integer endOffset,
                            String category, String severity, String message, String suggestion) {
        this.itemId = itemId;
        this.seq = seq;
        this.quote = quote;
        this.startOffset = startOffset;
        this.endOffset = endOffset;
        this.category = category;
        this.severity = severity;
        this.message = message;
        this.suggestion = suggestion;
    }

    public static FeedbackComment create(Long itemId, int seq, String quote, Integer startOffset, Integer endOffset,
                                         String category, String severity, String message, String suggestion) {
        return new FeedbackComment(itemId, seq, quote, startOffset, endOffset, category, severity, message, suggestion);
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

    public String getQuote() {
        return quote;
    }

    public Integer getStartOffset() {
        return startOffset;
    }

    public Integer getEndOffset() {
        return endOffset;
    }

    public String getCategory() {
        return category;
    }

    public String getSeverity() {
        return severity;
    }

    public String getMessage() {
        return message;
    }

    public String getSuggestion() {
        return suggestion;
    }
}

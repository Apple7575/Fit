package com.ssafy.companyanalysis.coverletter.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** 자소서 문항. */
@Entity
@Table(name = "cover_letter_item")
public class CoverLetterItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "cover_letter_id", nullable = false, updatable = false)
    private Long coverLetterId;

    @Column(name = "seq", nullable = false)
    private int seq;

    @Column(name = "question", nullable = false)
    private String question;

    @Column(name = "answer", nullable = false)
    private String answer;

    @Column(name = "char_limit", nullable = false)
    private int charLimit;

    protected CoverLetterItem() {
    }

    private CoverLetterItem(Long coverLetterId, int seq, String question, String answer, int charLimit) {
        this.coverLetterId = coverLetterId;
        this.seq = seq;
        this.question = question;
        this.answer = answer;
        this.charLimit = charLimit;
    }

    public static CoverLetterItem create(Long coverLetterId, int seq, String question, String answer, int charLimit) {
        return new CoverLetterItem(coverLetterId, seq, question, answer, charLimit);
    }

    public Long getId() {
        return id;
    }

    public Long getCoverLetterId() {
        return coverLetterId;
    }

    public int getSeq() {
        return seq;
    }

    public String getQuestion() {
        return question;
    }

    public String getAnswer() {
        return answer;
    }

    public int getCharLimit() {
        return charLimit;
    }
}

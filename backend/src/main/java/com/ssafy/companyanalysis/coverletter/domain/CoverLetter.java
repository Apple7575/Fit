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

    @Column(name = "updated_at", nullable = false)
    private OffsetDateTime updatedAt;

    protected CoverLetter() {
    }

    private CoverLetter(Long userId, String title, String targetCompany, String targetPosition) {
        this.userId = userId;
        this.title = title;
        this.targetCompany = targetCompany;
        this.targetPosition = targetPosition;
        this.updatedAt = OffsetDateTime.now();
    }

    public static CoverLetter create(Long userId, String title, String targetCompany, String targetPosition) {
        return new CoverLetter(userId, title, targetCompany, targetPosition);
    }

    public void update(String title, String targetCompany, String targetPosition) {
        this.title = title;
        this.targetCompany = targetCompany;
        this.targetPosition = targetPosition;
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

    public OffsetDateTime getUpdatedAt() {
        return updatedAt;
    }
}

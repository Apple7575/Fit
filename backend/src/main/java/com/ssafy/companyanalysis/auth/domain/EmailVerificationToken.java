package com.ssafy.companyanalysis.auth.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.OffsetDateTime;

/** 이메일 인증 링크 토큰. 원문은 메일 링크에만 있고 여기엔 해시만 저장한다. */
@Entity
@Table(name = "email_verification_token")
public class EmailVerificationToken {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Column(name = "token_hash", length = 64, nullable = false)
    private String tokenHash;

    @Column(name = "expires_at", nullable = false)
    private OffsetDateTime expiresAt;

    @Column(name = "used_at")
    private OffsetDateTime usedAt;

    protected EmailVerificationToken() {
    }

    private EmailVerificationToken(Long userId, String tokenHash, OffsetDateTime expiresAt) {
        this.userId = userId;
        this.tokenHash = tokenHash;
        this.expiresAt = expiresAt;
    }

    public static EmailVerificationToken issue(Long userId, String tokenHash, OffsetDateTime expiresAt) {
        return new EmailVerificationToken(userId, tokenHash, expiresAt);
    }

    public void markUsed(OffsetDateTime now) {
        this.usedAt = now;
    }

    public boolean isUsed() {
        return usedAt != null;
    }

    public boolean isExpired(OffsetDateTime now) {
        return now.isAfter(expiresAt);
    }

    public Long getUserId() {
        return userId;
    }

    public OffsetDateTime getExpiresAt() {
        return expiresAt;
    }
}

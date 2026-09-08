package com.ssafy.companyanalysis.auth.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.OffsetDateTime;

/**
 * 서비스 회원. 스키마는 Flyway 가 만들고 여기서는 매핑만 한다(ddl-auto=validate).
 * created_at/updated_at 은 DB 기본값이 채우므로 읽기 전용으로 둔다.
 */
@Entity
@Table(name = "users")
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "email", length = 255, nullable = false)
    private String email;

    @Column(name = "password_hash", length = 100, nullable = false)
    private String passwordHash;

    @Column(name = "nickname", length = 50, nullable = false)
    private String nickname;

    @Enumerated(EnumType.STRING)
    @Column(name = "role", length = 20, nullable = false)
    private Role role;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", length = 20, nullable = false)
    private UserStatus status;

    @Column(name = "created_at", nullable = false, insertable = false, updatable = false)
    private OffsetDateTime createdAt;

    @Column(name = "updated_at", nullable = false, insertable = false, updatable = false)
    private OffsetDateTime updatedAt;

    protected User() {
    }

    private User(String email, String passwordHash, String nickname) {
        this.email = email;
        this.passwordHash = passwordHash;
        this.nickname = nickname;
        this.role = Role.ROLE_USER;
        this.status = UserStatus.PENDING;
    }

    public static User create(String email, String passwordHash, String nickname) {
        return new User(email, passwordHash, nickname);
    }

    public void resetCredentials(String passwordHash, String nickname) {
        this.passwordHash = passwordHash;
        this.nickname = nickname;
        this.status = UserStatus.PENDING;
    }

    public void activate() {
        this.status = UserStatus.ACTIVE;
    }

    public Long getId() {
        return id;
    }

    public String getEmail() {
        return email;
    }

    public String getPasswordHash() {
        return passwordHash;
    }

    public String getNickname() {
        return nickname;
    }

    public Role getRole() {
        return role;
    }

    public UserStatus getStatus() {
        return status;
    }
}

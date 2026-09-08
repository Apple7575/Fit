package com.ssafy.companyanalysis.auth.repository;

import com.ssafy.companyanalysis.auth.domain.EmailVerificationToken;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;

public interface EmailVerificationTokenRepository extends JpaRepository<EmailVerificationToken, Long> {

    Optional<EmailVerificationToken> findByTokenHash(String tokenHash);

    void deleteByUserId(Long userId);

    @Query("SELECT t.userId FROM EmailVerificationToken t WHERE t.expiresAt < :now")
    List<Long> findUserIdsWithExpiredToken(@Param("now") OffsetDateTime now);

    void deleteByExpiresAtBefore(OffsetDateTime time);
}

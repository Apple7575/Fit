package com.ssafy.companyanalysis.auth.service;

import com.ssafy.companyanalysis.auth.domain.EmailVerificationToken;
import com.ssafy.companyanalysis.auth.domain.User;
import com.ssafy.companyanalysis.auth.domain.UserStatus;
import com.ssafy.companyanalysis.auth.repository.EmailVerificationTokenRepository;
import com.ssafy.companyanalysis.auth.repository.UserRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.Base64;
import java.util.HexFormat;

@Service
public class EmailVerificationService {

    private static final SecureRandom RANDOM = new SecureRandom();

    private final EmailVerificationTokenRepository tokenRepository;
    private final UserRepository userRepository;
    private final VerificationMailSender mailSender;
    private final Duration tokenTtl;

    public EmailVerificationService(EmailVerificationTokenRepository tokenRepository,
            UserRepository userRepository,
            VerificationMailSender mailSender,
            @Value("${app.verification.token-ttl}") Duration tokenTtl) {
        this.tokenRepository = tokenRepository;
        this.userRepository = userRepository;
        this.mailSender = mailSender;
        this.tokenTtl = tokenTtl;
    }

    @Transactional
    public void issue(User user) {
        tokenRepository.deleteByUserId(user.getId());

        String rawToken = generateRawToken();
        OffsetDateTime expiresAt = OffsetDateTime.now().plus(tokenTtl);
        tokenRepository.save(EmailVerificationToken.issue(user.getId(), hash(rawToken), expiresAt));

        mailSender.send(user.getEmail(), rawToken);
    }

    @Transactional
    public void verify(String rawToken) {
        EmailVerificationToken token = tokenRepository.findByTokenHash(hash(rawToken))
                .orElseThrow(() -> new BusinessException(ErrorCode.VERIFICATION_TOKEN_INVALID));

        User user = userRepository.findById(token.getUserId())
                .orElseThrow(() -> new BusinessException(ErrorCode.VERIFICATION_TOKEN_INVALID));

        if (user.getStatus() == UserStatus.ACTIVE) {
            return; // 링크 재클릭 등은 멱등 처리
        }

        OffsetDateTime now = OffsetDateTime.now();
        if (token.isUsed() || token.isExpired(now)) {
            throw new BusinessException(ErrorCode.VERIFICATION_TOKEN_INVALID);
        }

        user.activate();
        token.markUsed(now);
    }

    private String generateRawToken() {
        byte[] bytes = new byte[32];
        RANDOM.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    private String hash(String rawToken) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(rawToken.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}

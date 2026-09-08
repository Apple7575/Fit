package com.ssafy.companyanalysis.auth.service;

import com.ssafy.companyanalysis.auth.domain.UserStatus;
import com.ssafy.companyanalysis.auth.repository.EmailVerificationTokenRepository;
import com.ssafy.companyanalysis.auth.repository.UserRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.util.List;

@Component
public class PendingAccountCleanupJob {

    private static final Logger log = LoggerFactory.getLogger(PendingAccountCleanupJob.class);

    private final UserRepository userRepository;
    private final EmailVerificationTokenRepository tokenRepository;

    public PendingAccountCleanupJob(UserRepository userRepository,
            EmailVerificationTokenRepository tokenRepository) {
        this.userRepository = userRepository;
        this.tokenRepository = tokenRepository;
    }

    // 토큰이 만료된 PENDING 계정을 지운다. 계정 삭제 시 토큰은 FK CASCADE 로 함께 지워진다.
    @Scheduled(cron = "${app.verification.cleanup-cron:0 0 3 * * *}")
    @Transactional
    public void purgeStalePendingAccounts() {
        OffsetDateTime now = OffsetDateTime.now();

        List<Long> expiredUserIds = tokenRepository.findUserIdsWithExpiredToken(now);
        int removed = expiredUserIds.isEmpty()
                ? 0
                : userRepository.deleteByIdInAndStatus(expiredUserIds, UserStatus.PENDING);

        tokenRepository.deleteByExpiresAtBefore(now);

        if (removed > 0) {
            log.info("만료된 미인증 계정 {}건을 정리했다", removed);
        }
    }
}

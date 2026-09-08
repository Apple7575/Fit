package com.ssafy.companyanalysis.auth.service;

import com.ssafy.companyanalysis.auth.domain.UserStatus;
import com.ssafy.companyanalysis.auth.repository.EmailVerificationTokenRepository;
import com.ssafy.companyanalysis.auth.repository.UserRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class PendingAccountCleanupJobTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private EmailVerificationTokenRepository tokenRepository;

    @InjectMocks
    private PendingAccountCleanupJob job;

    @Test
    @DisplayName("토큰이 만료된 PENDING 계정을 삭제한다")
    void deletesPendingAccountsWithExpiredToken() {
        given(tokenRepository.findUserIdsWithExpiredToken(any())).willReturn(List.of(1L, 2L));

        job.purgeStalePendingAccounts();

        verify(userRepository).deleteByIdInAndStatus(List.of(1L, 2L), UserStatus.PENDING);
        verify(tokenRepository).deleteByExpiresAtBefore(any());
    }

    @Test
    @DisplayName("만료 토큰이 없으면 계정 삭제를 시도하지 않는다")
    void skipsUserDeletionWhenNothingExpired() {
        given(tokenRepository.findUserIdsWithExpiredToken(any())).willReturn(List.of());

        job.purgeStalePendingAccounts();

        verify(userRepository, never()).deleteByIdInAndStatus(any(), eq(UserStatus.PENDING));
        verify(tokenRepository).deleteByExpiresAtBefore(any());
    }
}

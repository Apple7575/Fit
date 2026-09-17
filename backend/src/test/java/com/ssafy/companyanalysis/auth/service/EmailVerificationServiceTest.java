package com.ssafy.companyanalysis.auth.service;

import com.ssafy.companyanalysis.auth.domain.EmailVerificationToken;
import com.ssafy.companyanalysis.auth.domain.User;
import com.ssafy.companyanalysis.auth.domain.UserStatus;
import com.ssafy.companyanalysis.auth.repository.EmailVerificationTokenRepository;
import com.ssafy.companyanalysis.auth.repository.UserRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class EmailVerificationServiceTest {

    @Mock
    private EmailVerificationTokenRepository tokenRepository;

    @Mock
    private UserRepository userRepository;

    @Mock
    private VerificationMailSender mailSender;

    private EmailVerificationService service;

    @BeforeEach
    void setUp() {
        service = new EmailVerificationService(tokenRepository, userRepository, mailSender, Duration.ofHours(24));
    }

    @Test
    @DisplayName("발급은 기존 토큰을 지우고 새 토큰을 저장한 뒤 메일을 보낸다")
    void issueReplacesTokenAndSendsMail() {
        User user = User.create("user@example.com", "hash", "민재");

        service.issue(user);

        verify(tokenRepository).deleteByUserId(user.getId());
        verify(tokenRepository).save(any(EmailVerificationToken.class));
        verify(mailSender).send(eq("user@example.com"), anyString());
    }

    @Test
    @DisplayName("유효한 토큰은 회원을 ACTIVE 로 바꾸고 토큰을 사용 처리한다")
    void verifyActivatesUser() {
        User user = User.create("user@example.com", "hash", "민재");
        EmailVerificationToken token =
                EmailVerificationToken.issue(1L, "h", OffsetDateTime.now().plusHours(1));
        given(tokenRepository.findByTokenHash(anyString())).willReturn(Optional.of(token));
        given(userRepository.findById(1L)).willReturn(Optional.of(user));

        service.verify("raw-token");

        assertThat(user.getStatus()).isEqualTo(UserStatus.ACTIVE);
        assertThat(token.isUsed()).isTrue();
    }

    @Test
    @DisplayName("없는 토큰은 VERIFICATION_TOKEN_INVALID")
    void verifyUnknownTokenFails() {
        given(tokenRepository.findByTokenHash(anyString())).willReturn(Optional.empty());

        assertThatThrownBy(() -> service.verify("raw-token"))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCode.VERIFICATION_TOKEN_INVALID);
    }

    @Test
    @DisplayName("만료된 토큰은 VERIFICATION_TOKEN_INVALID 이고 회원은 그대로다")
    void verifyExpiredTokenFails() {
        User user = User.create("user@example.com", "hash", "민재");
        EmailVerificationToken token =
                EmailVerificationToken.issue(1L, "h", OffsetDateTime.now().minusMinutes(1));
        given(tokenRepository.findByTokenHash(anyString())).willReturn(Optional.of(token));
        given(userRepository.findById(1L)).willReturn(Optional.of(user));

        assertThatThrownBy(() -> service.verify("raw-token"))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCode.VERIFICATION_TOKEN_INVALID);
        assertThat(user.getStatus()).isEqualTo(UserStatus.PENDING);
    }

    @Test
    @DisplayName("이미 사용된 토큰은 VERIFICATION_TOKEN_INVALID")
    void verifyUsedTokenFails() {
        User user = User.create("user@example.com", "hash", "민재");
        EmailVerificationToken token =
                EmailVerificationToken.issue(1L, "h", OffsetDateTime.now().plusHours(1));
        token.markUsed(OffsetDateTime.now());
        given(tokenRepository.findByTokenHash(anyString())).willReturn(Optional.of(token));
        given(userRepository.findById(1L)).willReturn(Optional.of(user));

        assertThatThrownBy(() -> service.verify("raw-token"))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCode.VERIFICATION_TOKEN_INVALID);
    }

    @Test
    @DisplayName("이미 인증된 회원은 만료 토큰이어도 멱등하게 성공한다")
    void verifyIsIdempotentForActiveUser() {
        User user = User.create("user@example.com", "hash", "민재");
        user.activate();
        EmailVerificationToken token =
                EmailVerificationToken.issue(1L, "h", OffsetDateTime.now().minusMinutes(1));
        given(tokenRepository.findByTokenHash(anyString())).willReturn(Optional.of(token));
        given(userRepository.findById(1L)).willReturn(Optional.of(user));

        service.verify("raw-token");

        assertThat(user.getStatus()).isEqualTo(UserStatus.ACTIVE);
    }
}

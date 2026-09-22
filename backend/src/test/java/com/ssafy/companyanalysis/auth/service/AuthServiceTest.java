package com.ssafy.companyanalysis.auth.service;

import com.ssafy.companyanalysis.auth.domain.User;
import com.ssafy.companyanalysis.auth.dto.SignupRequest;
import com.ssafy.companyanalysis.auth.dto.SignupResponse;
import com.ssafy.companyanalysis.auth.repository.UserRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class AuthServiceTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private PasswordEncoder passwordEncoder;

    @Mock
    private EmailVerificationService emailVerificationService;

    @InjectMocks
    private AuthService authService;

    @Test
    @DisplayName("새 이메일 가입은 회원을 만들고 인증 메일을 발급한다")
    void signupCreatesUserAndIssuesVerification() {
        given(userRepository.findByEmail("user@example.com")).willReturn(Optional.empty());
        given(passwordEncoder.encode("password123")).willReturn("{bcrypt}hash");
        given(userRepository.save(any(User.class))).willAnswer(invocation -> invocation.getArgument(0));

        SignupResponse response = authService.signup(new SignupRequest("user@example.com", "password123", "민재"));

        assertThat(response.email()).isEqualTo("user@example.com");
        verify(emailVerificationService).issue(any(User.class));
    }

    @Test
    @DisplayName("미인증 이메일 재가입은 자격을 갱신(리셋)하고 다시 발급한다")
    void signupResetsPendingAccount() {
        User pending = User.create("user@example.com", "old-hash", "옛닉");
        given(userRepository.findByEmail("user@example.com")).willReturn(Optional.of(pending));
        given(passwordEncoder.encode("password123")).willReturn("new-hash");

        authService.signup(new SignupRequest("user@example.com", "password123", "새닉"));

        assertThat(pending.getPasswordHash()).isEqualTo("new-hash");
        assertThat(pending.getNickname()).isEqualTo("새닉");
        verify(userRepository, never()).save(any());
        verify(emailVerificationService).issue(pending);
    }

    @Test
    @DisplayName("이미 인증된 이메일이면 EMAIL_ALREADY_EXISTS 로 막고 발급하지 않는다")
    void signupRejectsActiveEmail() {
        User active = User.create("user@example.com", "hash", "민재");
        active.activate();
        given(userRepository.findByEmail("user@example.com")).willReturn(Optional.of(active));
        given(passwordEncoder.encode("password123")).willReturn("new-hash");

        assertThatThrownBy(() -> authService.signup(new SignupRequest("user@example.com", "password123", "민재")))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCode.EMAIL_ALREADY_EXISTS);

        verify(emailVerificationService, never()).issue(any());
    }

    @Test
    @DisplayName("탈퇴 요청한 회원을 삭제한다")
    void withdrawDeletesUser() {
        User user = User.create("user@example.com", "{bcrypt}hash", "민재");
        given(userRepository.findById(1L)).willReturn(Optional.of(user));

        authService.withdraw(1L);

        verify(userRepository).delete(user);
    }
}

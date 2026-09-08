package com.ssafy.companyanalysis.auth.service;

import com.ssafy.companyanalysis.auth.domain.User;
import com.ssafy.companyanalysis.auth.domain.UserStatus;
import com.ssafy.companyanalysis.auth.dto.SignupRequest;
import com.ssafy.companyanalysis.auth.dto.SignupResponse;
import com.ssafy.companyanalysis.auth.repository.UserRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final EmailVerificationService emailVerificationService;

    public AuthService(UserRepository userRepository,
            PasswordEncoder passwordEncoder,
            EmailVerificationService emailVerificationService) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.emailVerificationService = emailVerificationService;
    }

    @Transactional
    public SignupResponse signup(SignupRequest request) {
        String passwordHash = passwordEncoder.encode(request.password());

        User user = userRepository.findByEmail(request.email())
                .map(existing -> reset(existing, passwordHash, request.nickname()))
                .orElseGet(() -> userRepository.save(
                        User.create(request.email(), passwordHash, request.nickname())));

        emailVerificationService.issue(user);
        return new SignupResponse(user.getEmail());
    }

    // 이미 인증된 계정이면 중복, 미인증(PENDING)이면 자격을 새로 받아 재발급한다.
    private User reset(User existing, String passwordHash, String nickname) {
        if (existing.getStatus() != UserStatus.PENDING) {
            throw new BusinessException(ErrorCode.EMAIL_ALREADY_EXISTS);
        }
        existing.resetCredentials(passwordHash, nickname);
        return existing;
    }
}

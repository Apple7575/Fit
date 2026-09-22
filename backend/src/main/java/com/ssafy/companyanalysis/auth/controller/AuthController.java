package com.ssafy.companyanalysis.auth.controller;

import com.ssafy.companyanalysis.auth.domain.UserStatus;
import com.ssafy.companyanalysis.auth.dto.LoginRequest;
import com.ssafy.companyanalysis.auth.dto.MeResponse;
import com.ssafy.companyanalysis.auth.dto.SignupRequest;
import com.ssafy.companyanalysis.auth.dto.SignupResponse;
import com.ssafy.companyanalysis.auth.dto.VerifyRequest;
import com.ssafy.companyanalysis.auth.service.AuthService;
import com.ssafy.companyanalysis.auth.service.EmailVerificationService;
import com.ssafy.companyanalysis.auth.service.UserPrincipal;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.global.response.ApiResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.logout.SecurityContextLogoutHandler;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final AuthService authService;
    private final EmailVerificationService emailVerificationService;
    private final AuthenticationManager authenticationManager;
    private final SecurityContextRepository securityContextRepository;

    public AuthController(AuthService authService,
            EmailVerificationService emailVerificationService,
            AuthenticationManager authenticationManager,
            SecurityContextRepository securityContextRepository) {
        this.authService = authService;
        this.emailVerificationService = emailVerificationService;
        this.authenticationManager = authenticationManager;
        this.securityContextRepository = securityContextRepository;
    }

    @PostMapping("/signup")
    public ApiResponse<SignupResponse> signup(@RequestBody @Valid SignupRequest request) {
        return ApiResponse.ok(authService.signup(request));
    }

    @PostMapping("/verify")
    public ApiResponse<Void> verify(@RequestBody @Valid VerifyRequest request) {
        emailVerificationService.verify(request.token());
        return ApiResponse.ok(null);
    }

    @PostMapping("/login")
    public ApiResponse<MeResponse> login(@RequestBody @Valid LoginRequest request,
            HttpServletRequest httpRequest, HttpServletResponse httpResponse) {
        Authentication authentication = authenticate(request);
        UserPrincipal principal = (UserPrincipal) authentication.getPrincipal();

        if (principal.getStatus() == UserStatus.PENDING) {
            throw new BusinessException(ErrorCode.EMAIL_NOT_VERIFIED);
        }

        SecurityContext context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(authentication);
        SecurityContextHolder.setContext(context);
        securityContextRepository.saveContext(context, httpRequest, httpResponse);

        return ApiResponse.ok(MeResponse.from(principal));
    }

    @PostMapping("/logout")
    public ApiResponse<Void> logout(HttpServletRequest httpRequest, HttpServletResponse httpResponse) {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        new SecurityContextLogoutHandler().logout(httpRequest, httpResponse, authentication);
        return ApiResponse.ok(null);
    }

    @GetMapping("/me")
    public ApiResponse<MeResponse> me(@AuthenticationPrincipal UserPrincipal principal) {
        return ApiResponse.ok(MeResponse.from(principal));
    }

    @DeleteMapping("/me")
    public ApiResponse<Void> withdraw(@AuthenticationPrincipal UserPrincipal principal,
            HttpServletRequest httpRequest, HttpServletResponse httpResponse) {
        authService.withdraw(principal.getId());
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        new SecurityContextLogoutHandler().logout(httpRequest, httpResponse, authentication);
        return ApiResponse.ok(null);
    }

    private Authentication authenticate(LoginRequest request) {
        try {
            return authenticationManager.authenticate(
                    new UsernamePasswordAuthenticationToken(request.email(), request.password()));
        } catch (AuthenticationException e) {
            throw new BusinessException(ErrorCode.INVALID_CREDENTIALS);
        }
    }
}

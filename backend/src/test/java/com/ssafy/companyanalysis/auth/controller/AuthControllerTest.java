package com.ssafy.companyanalysis.auth.controller;

import com.ssafy.companyanalysis.auth.domain.User;
import com.ssafy.companyanalysis.auth.dto.LoginRequest;
import com.ssafy.companyanalysis.auth.dto.SignupRequest;
import com.ssafy.companyanalysis.auth.dto.SignupResponse;
import com.ssafy.companyanalysis.auth.dto.VerifyRequest;
import com.ssafy.companyanalysis.auth.service.AuthService;
import com.ssafy.companyanalysis.auth.service.EmailVerificationService;
import com.ssafy.companyanalysis.auth.service.UserPrincipal;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.global.security.RestAccessDeniedHandler;
import com.ssafy.companyanalysis.global.security.RestAuthenticationEntryPoint;
import com.ssafy.companyanalysis.global.security.SecurityConfig;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import tools.jackson.databind.ObjectMapper;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(AuthController.class)
@Import({SecurityConfig.class, RestAuthenticationEntryPoint.class, RestAccessDeniedHandler.class})
class AuthControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockitoBean
    private AuthService authService;

    @MockitoBean
    private EmailVerificationService emailVerificationService;

    @MockitoBean
    private AuthenticationManager authenticationManager;

    private static UserPrincipal principal(User user) {
        return new UserPrincipal(user);
    }

    @Test
    @DisplayName("회원가입은 인증 메일 대상 이메일을 반환한다")
    void signupReturnsEmail() throws Exception {
        given(authService.signup(any())).willReturn(new SignupResponse("user@example.com"));

        mockMvc.perform(post("/api/auth/signup").with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                new SignupRequest("user@example.com", "Password123!", "민재"))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.email").value("user@example.com"));
    }

    @Test
    @DisplayName("이미 인증된 이메일이면 409 EMAIL_ALREADY_EXISTS")
    void signupWithActiveEmailIsConflict() throws Exception {
        given(authService.signup(any())).willThrow(new BusinessException(ErrorCode.EMAIL_ALREADY_EXISTS));

        mockMvc.perform(post("/api/auth/signup").with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                new SignupRequest("user@example.com", "Password123!", "민재"))))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.error.code").value("EMAIL_ALREADY_EXISTS"));
    }

    @Test
    @DisplayName("길이만 맞고 복잡도(영문·숫자·특수문자)를 못 채우면 400 INVALID_PARAMETER")
    void signupWithWeakPasswordIsBadRequest() throws Exception {
        mockMvc.perform(post("/api/auth/signup").with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                new SignupRequest("user@example.com", "password123", "민재"))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    @Test
    @DisplayName("형식에 맞지 않는 가입 요청은 400 INVALID_PARAMETER")
    void signupWithInvalidBodyIsBadRequest() throws Exception {
        mockMvc.perform(post("/api/auth/signup").with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                new SignupRequest("not-an-email", "short", "민재"))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    @Test
    @DisplayName("유효한 토큰의 인증 요청은 200")
    void verifyReturnsOk() throws Exception {
        mockMvc.perform(post("/api/auth/verify").with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new VerifyRequest("token-123"))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true));
    }

    @Test
    @DisplayName("유효하지 않은 토큰은 400 VERIFICATION_TOKEN_INVALID")
    void verifyWithInvalidTokenIsBadRequest() throws Exception {
        willThrow(new BusinessException(ErrorCode.VERIFICATION_TOKEN_INVALID))
                .given(emailVerificationService).verify(anyString());

        mockMvc.perform(post("/api/auth/verify").with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new VerifyRequest("bad-token"))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("VERIFICATION_TOKEN_INVALID"));
    }

    @Test
    @DisplayName("인증된 회원의 로그인은 성공한다")
    void loginReturnsMember() throws Exception {
        User user = User.create("user@example.com", "hash", "민재");
        user.activate();
        Authentication authentication = new UsernamePasswordAuthenticationToken(
                principal(user), null, principal(user).getAuthorities());
        given(authenticationManager.authenticate(any())).willReturn(authentication);

        mockMvc.perform(post("/api/auth/login").with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                new LoginRequest("user@example.com", "password123"))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.email").value("user@example.com"))
                .andExpect(jsonPath("$.data.nickname").value("민재"));
    }

    @Test
    @DisplayName("미인증(PENDING) 회원의 로그인은 403 EMAIL_NOT_VERIFIED")
    void loginWithPendingUserIsForbidden() throws Exception {
        User user = User.create("user@example.com", "hash", "민재");
        Authentication authentication = new UsernamePasswordAuthenticationToken(
                principal(user), null, principal(user).getAuthorities());
        given(authenticationManager.authenticate(any())).willReturn(authentication);

        mockMvc.perform(post("/api/auth/login").with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                new LoginRequest("user@example.com", "password123"))))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.error.code").value("EMAIL_NOT_VERIFIED"));
    }

    @Test
    @DisplayName("자격증명이 틀리면 401 INVALID_CREDENTIALS")
    void loginWithBadCredentialsIsUnauthorized() throws Exception {
        given(authenticationManager.authenticate(any())).willThrow(new BadCredentialsException("bad"));

        mockMvc.perform(post("/api/auth/login").with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                new LoginRequest("user@example.com", "wrong-password"))))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.error.code").value("INVALID_CREDENTIALS"));
    }

    @Test
    @DisplayName("로그아웃은 200 을 반환한다")
    void logoutReturnsOk() throws Exception {
        mockMvc.perform(post("/api/auth/logout").with(csrf()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true));
    }

    @Test
    @DisplayName("로그인 상태에서 내 정보를 조회한다")
    void meReturnsCurrentUser() throws Exception {
        User user = User.create("user@example.com", "hash", "민재");
        user.activate();

        mockMvc.perform(get("/api/auth/me").with(user(principal(user))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.email").value("user@example.com"))
                .andExpect(jsonPath("$.data.nickname").value("민재"));
    }

    @Test
    @DisplayName("비로그인 상태의 내 정보 조회는 401 UNAUTHENTICATED")
    void meWithoutLoginIsUnauthorized() throws Exception {
        mockMvc.perform(get("/api/auth/me"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.error.code").value("UNAUTHENTICATED"));
    }

    @Test
    @DisplayName("현재 비밀번호를 확인하고 회원탈퇴한 뒤 세션을 끝낸다")
    void withdrawReturnsOk() throws Exception {
        User user = User.create("user@example.com", "hash", "민재");
        user.activate();

        mockMvc.perform(delete("/api/auth/me").with(user(principal(user))).with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"password\":\"password123\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true));
    }

    @Test
    @DisplayName("비로그인 상태의 회원탈퇴는 401 UNAUTHENTICATED")
    void withdrawWithoutLoginIsUnauthorized() throws Exception {
        mockMvc.perform(delete("/api/auth/me").with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"password\":\"password123\"}"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.error.code").value("UNAUTHENTICATED"));
    }
}

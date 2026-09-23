package com.ssafy.companyanalysis.auth.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;

/**
 * 로그인 요청.
 *
 * @param rememberMe "로그인 유지" 를 켠 경우. 세션과 별개로 오래 가는 쿠키를 하나 더 받는다.
 *                   보내지 않으면 false — 공용 PC 에서 켜질 일이 없도록 꺼진 쪽이 기본이다.
 */
public record LoginRequest(
        @NotBlank(message = "이메일을 입력해 주세요.")
        @Email(message = "이메일 주소 형식이 올바르지 않습니다.")
        String email,
        @NotBlank(message = "비밀번호를 입력해 주세요.") String password,
        boolean rememberMe) {
}

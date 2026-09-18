package com.ssafy.companyanalysis.auth.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record SignupRequest(
        @NotBlank @Email @Size(max = 255) String email,
        // 영문·숫자·특수문자를 모두 포함해 8~64자. 메시지는 로그로만 남고(공통 봉투가 가림),
        // 사용자에게 보이는 안내는 프론트(SignupPage)가 같은 규칙으로 담당한다.
        @NotBlank
        @Pattern(
                regexp = "^(?=.*[A-Za-z])(?=.*\\d)(?=.*[^A-Za-z0-9]).{8,64}$",
                message = "비밀번호는 영문·숫자·특수문자를 포함해 8자 이상이어야 합니다.")
        String password,
        @NotBlank @Size(max = 50) String nickname) {
}

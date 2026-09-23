package com.ssafy.companyanalysis.auth.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record SignupRequest(
        @NotBlank(message = "이메일을 입력해 주세요.")
        @Email(message = "이메일 주소 형식이 올바르지 않습니다.")
        @Size(max = 255, message = "이메일이 너무 깁니다.")
        String email,
        // 영문·숫자·특수문자를 모두 포함해 8~64자. 프론트(SignupPage)가 같은 규칙으로 먼저
        // 안내하고, 그 그물을 빠져나온 요청에는 여기 적은 문구가 그대로 사용자에게 간다.
        @NotBlank(message = "비밀번호를 입력해 주세요.")
        @Pattern(
                regexp = "^(?=.*[A-Za-z])(?=.*\\d)(?=.*[^A-Za-z0-9]).{8,64}$",
                message = "비밀번호는 영문·숫자·특수문자를 포함해 8자 이상이어야 합니다.")
        String password,
        @NotBlank(message = "닉네임을 입력해 주세요.")
        @Size(max = 50, message = "닉네임은 50자까지 쓸 수 있습니다.")
        String nickname) {
}

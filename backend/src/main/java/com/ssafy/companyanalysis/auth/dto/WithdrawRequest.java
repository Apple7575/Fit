package com.ssafy.companyanalysis.auth.dto;

import jakarta.validation.constraints.NotBlank;

/** 회원탈퇴 직전 본인 확인용 현재 비밀번호. */
public record WithdrawRequest(
        @NotBlank(message = "비밀번호를 입력해 주세요.")
        String password
) {
}

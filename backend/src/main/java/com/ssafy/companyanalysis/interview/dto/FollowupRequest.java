package com.ssafy.companyanalysis.interview.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/** 직전 답변 기반 꼬리질문 요청(무저장, 로그인 전용). */
public record FollowupRequest(
        @NotBlank @Size(max = 1000) String question,
        @NotBlank @Size(max = 6000) String transcript,
        @Size(max = 120) String targetPosition) {
}

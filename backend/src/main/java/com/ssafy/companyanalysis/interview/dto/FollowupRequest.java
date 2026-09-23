package com.ssafy.companyanalysis.interview.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/** 직전 답변 기반 꼬리질문 요청(무저장, 로그인 전용). */
public record FollowupRequest(
        @NotBlank @Size(max = 1000) String question,
        @NotBlank(message = "답변을 입력해 주세요.")
        @Size(max = 6000, message = "답변은 6000자까지 보낼 수 있습니다.")
        String transcript,
        @Size(max = 120, message = "지원 직무는 120자까지 쓸 수 있습니다.") String targetPosition) {
}

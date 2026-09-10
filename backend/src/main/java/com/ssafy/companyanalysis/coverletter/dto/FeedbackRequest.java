package com.ssafy.companyanalysis.coverletter.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

/** 문항 1개 AI 피드백 요청(무저장, 공개). */
public record FeedbackRequest(
        @NotBlank @Size(max = 500) String question,
        @NotBlank @Size(max = 4000) String answer,
        @NotNull @Min(1) @Max(4000) Integer charLimit,
        @Size(max = 120) String targetPosition) {
}

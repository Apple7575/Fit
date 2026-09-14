package com.ssafy.companyanalysis.interview.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/** 면접 질문 생성 요청(무저장, 로그인 전용). corpCode 가 있으면 기업 데이터로 그라운딩한다. */
public record QuestionGenerateRequest(
        @Size(max = 20) String corpCode,
        @Size(max = 120) String targetCompany,
        @Size(max = 120) String targetPosition,
        @Pattern(regexp = "technical|behavioral", message = "면접 유형은 technical 또는 behavioral 이어야 합니다.")
        String interviewType,
        Long coverLetterId,
        @NotNull @Min(3) @Max(7) Integer questionCount) {
}

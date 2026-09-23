package com.ssafy.companyanalysis.interview.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/** 면접 질문 생성 요청(무저장, 로그인 전용). corpCode 가 있으면 기업 데이터로 그라운딩한다. */
public record QuestionGenerateRequest(
        @Size(max = 20) String corpCode,
        @Size(max = 120, message = "지원 회사는 120자까지 쓸 수 있습니다.") String targetCompany,
        @Size(max = 120, message = "지원 직무는 120자까지 쓸 수 있습니다.") String targetPosition,
        // 규칙을 그대로 읽어 주면("technical 또는 behavioral") 받은 사람이 할 일을 알 수 없다.
        // 화면에 보이는 말로 적는다.
        @Pattern(regexp = "technical|behavioral", message = "면접 유형을 기술 면접과 인성 면접 중에서 골라 주세요.")
        String interviewType,
        Long coverLetterId,
        @NotNull(message = "질문 수를 정해 주세요.")
        @Min(value = 3, message = "질문 수는 3개에서 7개 사이로 정해 주세요.")
        @Max(value = 7, message = "질문 수는 3개에서 7개 사이로 정해 주세요.")
        Integer questionCount) {
}

package com.ssafy.companyanalysis.interview.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.util.List;

/** 모의 면접 저장 요청(로그인 전용). 저장 후 수정하지 않는다(불변). */
public record InterviewSaveRequest(
        @Size(max = 120) String targetCompany,
        @Size(max = 120) String targetPosition,
        @NotBlank @Pattern(regexp = "technical|behavioral") String interviewType,
        Long coverLetterId,
        @Size(max = 2000) String overallSummary,
        // AnalyzeRequest 와 같은 이유. 저장도 개수를 막아야 DB 가 부풀지 않는다
        @NotEmpty @Size(max = 20) @Valid List<Item> items) {

    // 프론트가 보내는 부가 필드는 무시한다.
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Item(
            @NotBlank @Size(max = 1000) String question,
            @Pattern(regexp = "company|cover_letter|common|followup") String sourceType,
            @Size(max = 6000) String transcript,
            @Size(max = 2000) String feedbackSummary,
            @Valid List<Point> points) {
    }

    public record Point(
            @NotBlank @Pattern(regexp = "STRENGTH|IMPROVEMENT") String kind,
            @NotBlank @Pattern(regexp = "질문적합성|구체성|논리성|기업직무이해|전달력") String category,
            @NotBlank String message,
            String suggestion) {
    }
}

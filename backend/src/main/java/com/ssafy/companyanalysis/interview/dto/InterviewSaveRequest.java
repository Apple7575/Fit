package com.ssafy.companyanalysis.interview.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.util.List;

/**
 * 모의 면접 저장 요청(로그인 전용). 저장 후 수정하지 않는다(불변).
 *
 * <p>사람이 치거나 말한 칸(회사·직무·답변)에만 안내를 적어 둔다. 면접 유형·질문 출처처럼
 * 화면이 골라 채우는 값은 사용자가 고칠 수 있는 것이 아니라서 적지 않는다 — 적지 않으면
 * 고정 문구로 나간다(GlobalExceptionHandler 참고).
 */
public record InterviewSaveRequest(
        @Size(max = 120, message = "지원 회사는 120자까지 쓸 수 있습니다.") String targetCompany,
        @Size(max = 120, message = "지원 직무는 120자까지 쓸 수 있습니다.") String targetPosition,
        @NotBlank @Pattern(regexp = "technical|behavioral") String interviewType,
        Long coverLetterId,
        @Size(max = 2000) String overallSummary,
        // AnalyzeRequest 와 같은 이유. 저장도 개수를 막아야 DB 가 부풀지 않는다
        @NotEmpty(message = "저장할 답변이 없습니다.")
        @Size(max = 20, message = "한 번에 20문항까지 저장할 수 있습니다.")
        @Valid List<Item> items) {

    // 프론트가 보내는 부가 필드는 무시한다.
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Item(
            @NotBlank @Size(max = 1000) String question,
            @Pattern(regexp = "company|cover_letter|common|followup") String sourceType,
            @Size(max = 6000, message = "답변은 6000자까지 저장할 수 있습니다.") String transcript,
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

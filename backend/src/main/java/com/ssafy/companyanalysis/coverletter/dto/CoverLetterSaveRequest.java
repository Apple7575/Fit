package com.ssafy.companyanalysis.coverletter.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.util.List;

/** 자소서 저장(신규·수정 공통) 요청. */
public record CoverLetterSaveRequest(
        @NotBlank @Size(max = 120) String title,
        @Size(max = 120) String targetCompany,
        @Size(max = 120) String targetPosition,
        @NotEmpty @Valid List<Item> items) {

    public record Item(
            @NotBlank @Size(max = 500) String question,
            @NotBlank @Size(max = 4000) String answer,
            @NotNull @Min(1) @Max(4000) Integer charLimit,
            @Valid Feedback feedback) {
    }

    // 프론트가 보내는 model 등 미사용 필드는 무시한다.
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Feedback(
            @Size(max = 2000) String summary,
            @Valid List<Comment> comments) {
    }

    public record Comment(
            @NotBlank String quote,
            Integer startOffset,
            Integer endOffset,
            @NotBlank @Pattern(regexp = "직무적합성|구체성|논리성|가독성|맞춤법") String category,
            @NotBlank @Pattern(regexp = "WARNING|SUGGESTION|INFO") String severity,
            @NotBlank String message,
            String suggestion) {
    }
}

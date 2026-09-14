package com.ssafy.companyanalysis.interview.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Size;

import java.util.List;

/** 문항 답변 일괄 분석 요청(무저장, 로그인 전용). transcript 는 무응답이면 빈 값일 수 있다. */
public record AnalyzeRequest(
        @Size(max = 20) String interviewType,
        @Size(max = 120) String targetPosition,
        @NotEmpty @Valid List<Item> items) {

    public record Item(
            @NotBlank @Size(max = 1000) String question,
            @Size(max = 20) String sourceType,
            @Size(max = 6000) String transcript) {
    }
}

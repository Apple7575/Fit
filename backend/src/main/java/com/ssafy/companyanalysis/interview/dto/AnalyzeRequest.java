package com.ssafy.companyanalysis.interview.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Size;

import java.util.List;

/** 문항 답변 일괄 분석 요청(무저장, 로그인 전용). transcript 는 무응답이면 빈 값일 수 있다. */
public record AnalyzeRequest(
        @Size(max = 20) String interviewType,
        @Size(max = 120, message = "지원 직무는 120자까지 쓸 수 있습니다.") String targetPosition,
        // 문항은 3~7개(QuestionGenerateRequest)이고 문항마다 꼬리질문이 하나씩 붙을 수 있다.
        // 상한이 없으면 문항 수백 개를 한 요청에 담아 보낼 수 있고, 그대로 LLM 으로 간다.
        @NotEmpty(message = "분석할 답변이 없습니다.")
        @Size(max = 20, message = "한 번에 20문항까지 분석할 수 있습니다.")
        @Valid List<Item> items) {

    public record Item(
            @NotBlank @Size(max = 1000) String question,
            @Size(max = 20) String sourceType,
            @Size(max = 6000, message = "답변은 6000자까지 분석할 수 있습니다.") String transcript) {
    }
}

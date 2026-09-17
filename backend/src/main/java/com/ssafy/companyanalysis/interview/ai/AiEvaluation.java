package com.ssafy.companyanalysis.interview.ai;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import java.util.List;

/** LLM 답변 평가 결과. items 순서는 입력 문항 순서와 같다. */
@JsonIgnoreProperties(ignoreUnknown = true)
public record AiEvaluation(String overallSummary, List<AiItem> items) {

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record AiItem(String feedbackSummary, List<AiPoint> points) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record AiPoint(String kind, String category, String message, String suggestion) {
    }
}

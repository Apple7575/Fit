package com.ssafy.companyanalysis.interview.ai;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import java.util.List;

/** LLM 이 생성한 면접 질문 목록. 순서가 곧 면접 진행 순서다. */
@JsonIgnoreProperties(ignoreUnknown = true)
public record AiQuestions(List<AiQuestion> questions) {

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record AiQuestion(String question, String sourceType) {
    }
}

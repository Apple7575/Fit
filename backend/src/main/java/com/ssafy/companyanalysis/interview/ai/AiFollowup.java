package com.ssafy.companyanalysis.interview.ai;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

/** LLM 이 만든 꼬리질문. basis 는 어떤 답변 내용에서 나왔는지 근거다. */
@JsonIgnoreProperties(ignoreUnknown = true)
public record AiFollowup(String question, String basis) {
}

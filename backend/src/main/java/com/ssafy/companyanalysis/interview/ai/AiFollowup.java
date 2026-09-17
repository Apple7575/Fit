package com.ssafy.companyanalysis.interview.ai;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

/**
 * LLM 이 만든 꼬리질문. needed 가 false 면 더 물을 가치가 없다는 뜻이라 질문을 만들지 않는다.
 * basis 는 어떤 답변 내용에서 나왔는지 근거다.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record AiFollowup(Boolean needed, String question, String basis) {
}

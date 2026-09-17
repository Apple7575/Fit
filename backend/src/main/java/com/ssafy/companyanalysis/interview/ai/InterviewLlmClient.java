package com.ssafy.companyanalysis.interview.ai;

/**
 * 면접 LLM provider 추상화. 구현체는 vLLM(개발) / GMS-Gemini(시연·최종) 이며
 * app.ai.interview.provider 로 하나만 활성화된다. 프롬프트는 서비스가 만들고,
 * 구현체는 전송·구조화 출력 파싱만 맡는다.
 */
public interface InterviewLlmClient {

    /** 면접 질문을 생성한다. */
    AiQuestions generateQuestions(String systemInstruction, String userText);

    /** 문항 답변들을 평가해 총평 + 문항별 피드백을 만든다. */
    AiEvaluation evaluateAnswers(String systemInstruction, String userText);

    /** 직전 답변 내용에서 꼬리질문 1개를 만든다. */
    AiFollowup generateFollowup(String systemInstruction, String userText);
}

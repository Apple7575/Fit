package com.ssafy.companyanalysis.agent.ai;

import com.ssafy.companyanalysis.coverletter.ai.GmsProperties;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import tools.jackson.databind.JsonNode;

import java.util.List;
import java.util.Map;

/**
 * 에이전트용 범용 LLM 호출. 기존 {@code GmsFeedbackClient} 는 문항 피드백 전용으로 프롬프트와
 * 응답 스키마가 박혀 있어 재사용할 수 없어서, 같은 RestClient 빈만 공유한다.
 *
 * <p>에이전트마다 지시문이 다르므로 지시문을 인자로 받고 평문을 돌려준다.
 */
@Component
public class AgentLlmClient {

    private final RestClient gmsRestClient;
    private final GmsProperties properties;

    public AgentLlmClient(RestClient gmsRestClient, GmsProperties properties) {
        this.gmsRestClient = gmsRestClient;
        this.properties = properties;
    }

    public boolean isAvailable() {
        return properties.hasKey();
    }

    /**
     * @param systemInstruction 에이전트의 역할 지시문
     * @param userText          자소서 본문 등 분석 대상
     * @return 모델이 만든 평문. 비어 있으면 실패로 본다
     */
    public String generate(String systemInstruction, String userText) {
        if (!properties.hasKey()) {
            throw new BusinessException(ErrorCode.AI_FEEDBACK_UNAVAILABLE);
        }

        JsonNode response;
        try {
            response = gmsRestClient.post()
                    .uri("/generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                            properties.model())
                    .header("x-goog-api-key", properties.key())
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(Map.of(
                            "systemInstruction", Map.of("parts", List.of(Map.of("text", systemInstruction))),
                            "contents", List.of(Map.of("parts", List.of(Map.of("text", userText)))),
                            "generationConfig", Map.of("temperature", 0.4)))
                    .retrieve()
                    .body(JsonNode.class);
        } catch (RestClientException e) {
            throw new BusinessException(ErrorCode.AI_FEEDBACK_FAILED);
        }

        String text = extractText(response);
        if (text == null || text.isBlank()) {
            throw new BusinessException(ErrorCode.AI_FEEDBACK_FAILED, "모델이 빈 응답을 돌려줬습니다.");
        }
        return text.trim();
    }

    private static String extractText(JsonNode response) {
        if (response == null) {
            return null;
        }
        JsonNode parts = response.path("candidates").path(0).path("content").path("parts");
        StringBuilder joined = new StringBuilder();
        for (JsonNode part : parts) {
            joined.append(part.path("text").asString(""));
        }
        return joined.toString();
    }
}

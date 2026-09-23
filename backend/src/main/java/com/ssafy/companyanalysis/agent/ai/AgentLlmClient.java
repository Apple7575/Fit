package com.ssafy.companyanalysis.agent.ai;

import com.ssafy.companyanalysis.coverletter.ai.GmsProperties;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.global.text.PlainText;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;
import tools.jackson.databind.JsonNode;

import java.util.List;
import java.util.Map;

/**
 * 에이전트용 범용 LLM 호출. {@code AiClientConfig} 의 RestClient 빈을 면접 기능과 함께 쓴다.
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
        return generate(systemInstruction, userText, Map.of("temperature", 0.4), true);
    }

    /**
     * JSON 만 돌려받는다. 모델이 설명이나 코드펜스를 덧붙이지 못하게 응답 형식을 못박는다.
     * 뽑아내기처럼 답이 하나로 정해지는 일에 쓰므로 temperature 도 낮춘다.
     */
    public String generateJson(String systemInstruction, String userText) {
        return generate(systemInstruction, userText,
                Map.of("temperature", 0.1, "responseMimeType", "application/json"), false);
    }

    private String generate(String systemInstruction, String userText,
                            Map<String, Object> generationConfig, boolean stripMarkdown) {
        if (!properties.hasKey()) {
            throw new BusinessException(ErrorCode.AI_UNAVAILABLE);
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
                            "generationConfig", generationConfig))
                    .retrieve()
                    .body(JsonNode.class);
        } catch (RestClientResponseException e) {
            if (e.getStatusCode().value() == 429) {
                throw new BusinessException(ErrorCode.AI_RATE_LIMITED);
            }
            throw new BusinessException(ErrorCode.AI_FAILED);
        } catch (RestClientException e) {
            throw new BusinessException(ErrorCode.AI_FAILED);
        }

        String text = extractText(response);
        if (text == null || text.isBlank()) {
            throw new BusinessException(ErrorCode.AI_FAILED, "모델이 빈 응답을 돌려줬습니다.");
        }
        // 화면이 평문으로 뿌리므로 마크다운 기호가 그대로 보인다. 프롬프트로 이르지만 자주 어긴다.
        // JSON 은 사람이 읽는 글이 아니라 그대로 파싱한다 — 값에 * 나 # 가 있으면 벗겨서 망가진다.
        return stripMarkdown ? PlainText.of(text) : text;
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

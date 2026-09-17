package com.ssafy.companyanalysis.interview.ai;

import com.ssafy.companyanalysis.coverletter.ai.GmsProperties;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

import java.util.List;
import java.util.Map;

/** GMS(Gemini) 구현. 시연·최종 provider. 자소서 기능의 gmsRestClient/GmsProperties 를 재사용한다. */
@Component
@ConditionalOnProperty(name = "app.ai.interview.provider", havingValue = "gms")
public class GmsClient implements InterviewLlmClient {

    private final RestClient gmsRestClient;
    private final GmsProperties properties;
    private final ObjectMapper objectMapper;

    public GmsClient(RestClient gmsRestClient, GmsProperties properties, ObjectMapper objectMapper) {
        this.gmsRestClient = gmsRestClient;
        this.properties = properties;
        this.objectMapper = objectMapper;
    }

    @Override
    public AiQuestions generateQuestions(String systemInstruction, String userText) {
        return complete(systemInstruction, userText, InterviewSchema.questions("upper"), AiQuestions.class);
    }

    @Override
    public AiEvaluation evaluateAnswers(String systemInstruction, String userText) {
        return complete(systemInstruction, userText, InterviewSchema.evaluation("upper"), AiEvaluation.class);
    }

    @Override
    public AiFollowup generateFollowup(String systemInstruction, String userText) {
        return complete(systemInstruction, userText, InterviewSchema.followup("upper"), AiFollowup.class);
    }

    private <T> T complete(String systemInstruction, String userText, Map<String, Object> schema, Class<T> type) {
        if (!properties.hasKey()) {
            throw new BusinessException(ErrorCode.INTERVIEW_AI_UNAVAILABLE);
        }
        JsonNode response;
        try {
            response = gmsRestClient.post()
                    .uri("/generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", properties.model())
                    .header("x-goog-api-key", properties.key())
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(requestBody(systemInstruction, userText, schema))
                    .retrieve()
                    .body(JsonNode.class);
        } catch (RestClientException e) {
            throw new BusinessException(ErrorCode.INTERVIEW_AI_FAILED);
        }
        return parse(response, type);
    }

    private Map<String, Object> requestBody(String systemInstruction, String userText, Map<String, Object> schema) {
        return Map.of(
                "systemInstruction", Map.of("parts", List.of(Map.of("text", systemInstruction))),
                "contents", List.of(Map.of("parts", List.of(Map.of("text", userText)))),
                "generationConfig", Map.of(
                        "responseMimeType", "application/json",
                        "responseSchema", schema,
                        "temperature", 0.4));
    }

    private <T> T parse(JsonNode response, Class<T> type) {
        if (response == null) {
            throw new BusinessException(ErrorCode.INTERVIEW_AI_FAILED);
        }
        JsonNode textNode = response.path("candidates").path(0).path("content").path("parts").path(0).path("text");
        if (!textNode.isString()) {
            throw new BusinessException(ErrorCode.INTERVIEW_AI_FAILED);
        }
        try {
            return objectMapper.readValue(textNode.asString(), type);
        } catch (RuntimeException e) {
            throw new BusinessException(ErrorCode.INTERVIEW_AI_FAILED);
        }
    }
}

package com.ssafy.companyanalysis.interview.ai;

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

/** vLLM(OpenAI 호환) 구현. 개발 기본 provider. Qwen3 는 enable_thinking=false 로 추론 출력을 끈다. */
@Component
@ConditionalOnProperty(name = "app.ai.interview.provider", havingValue = "vllm", matchIfMissing = true)
public class VllmClient implements InterviewLlmClient {

    private final RestClient vllmRestClient;
    private final VllmProperties properties;
    private final ObjectMapper objectMapper;

    public VllmClient(RestClient vllmRestClient, VllmProperties properties, ObjectMapper objectMapper) {
        this.vllmRestClient = vllmRestClient;
        this.properties = properties;
        this.objectMapper = objectMapper;
    }

    @Override
    public AiQuestions generateQuestions(String systemInstruction, String userText) {
        return complete(systemInstruction, userText, InterviewSchema.questions("lower"), AiQuestions.class);
    }

    @Override
    public AiEvaluation evaluateAnswers(String systemInstruction, String userText) {
        return complete(systemInstruction, userText, InterviewSchema.evaluation("lower"), AiEvaluation.class);
    }

    @Override
    public AiFollowup generateFollowup(String systemInstruction, String userText) {
        return complete(systemInstruction, userText, InterviewSchema.followup("lower"), AiFollowup.class);
    }

    private <T> T complete(String systemInstruction, String userText, Map<String, Object> schema, Class<T> type) {
        if (!properties.hasKey()) {
            throw new BusinessException(ErrorCode.INTERVIEW_AI_UNAVAILABLE);
        }
        JsonNode response;
        try {
            response = vllmRestClient.post()
                    .uri("/v1/chat/completions")
                    .header("Authorization", "Bearer " + properties.key())
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
                "model", properties.model(),
                "messages", List.of(
                        Map.of("role", "system", "content", systemInstruction),
                        Map.of("role", "user", "content", userText)),
                "temperature", 0.4,
                "max_tokens", 2000,
                // Qwen3 기본 사고(thinking) 출력을 끈다. 켜 두면 JSON 앞에 <think> 가 섞인다.
                "chat_template_kwargs", Map.of("enable_thinking", false),
                "response_format", Map.of(
                        "type", "json_schema",
                        "json_schema", Map.of("name", "output", "schema", schema)));
    }

    private <T> T parse(JsonNode response, Class<T> type) {
        if (response == null) {
            throw new BusinessException(ErrorCode.INTERVIEW_AI_FAILED);
        }
        JsonNode textNode = response.path("choices").path(0).path("message").path("content");
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

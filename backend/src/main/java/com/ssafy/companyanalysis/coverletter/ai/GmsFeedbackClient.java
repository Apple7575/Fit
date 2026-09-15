package com.ssafy.companyanalysis.coverletter.ai;

import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.global.text.PlainText;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

import java.util.List;
import java.util.Map;

/** GMS 프록시로 Gemini 를 호출해 문항을 평가한다. 구조화 출력(responseSchema)으로 JSON 을 강제받는다. */
@Component
public class GmsFeedbackClient {

    private static final String SYSTEM_INSTRUCTION = """
            너는 한국어 자기소개서 피드백 전문가다. 아래 문항의 답변을 평가한다.
            평가 기준: 직무적합성, 구체성(STAR), 논리성, 가독성, 맞춤법.
            규칙:
            - 각 코멘트의 quote 는 반드시 답변(answer) 안에 그대로 존재하는 부분 문자열이어야 한다.
            - 하나의 quote(같은 구간)에는 코멘트를 하나만 단다. 같은 부분에 대한 여러 관점의 지적은 하나의 코멘트로 합치고, 서로 다른 코멘트는 서로 다른 구간을 인용한다.
            - category 는 [직무적합성, 구체성, 논리성, 가독성, 맞춤법] 중 하나.
            - severity 는 WARNING(개선 필요), SUGGESTION(제안), INFO(참고) 중 하나.
            - summary 는 2~3문장 총평. 코멘트는 최대 6개, 답변 본문에 나타나는 순서대로.
            - summary, message, suggestion 에 마크다운을 쓰지 않는다. 별표(**), 우물정(#), 백틱(`)
              같은 기호 없이 줄글로만 쓴다. 화면이 그대로 뿌리기 때문에 기호가 글에 섞여 보인다.
              단 quote 는 답변에서 그대로 떼어 온 글이므로 손대지 않는다.
            """;

    private final RestClient gmsRestClient;
    private final GmsProperties properties;
    private final ObjectMapper objectMapper;

    public GmsFeedbackClient(RestClient gmsRestClient, GmsProperties properties, ObjectMapper objectMapper) {
        this.gmsRestClient = gmsRestClient;
        this.properties = properties;
        this.objectMapper = objectMapper;
    }

    public AiFeedback generate(String question, String answer, int charLimit, String targetPosition) {
        if (!properties.hasKey()) {
            throw new BusinessException(ErrorCode.AI_FEEDBACK_UNAVAILABLE);
        }

        JsonNode response;
        try {
            response = gmsRestClient.post()
                    .uri("/generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", properties.model())
                    .header("x-goog-api-key", properties.key())
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(requestBody(question, answer, charLimit, targetPosition))
                    .retrieve()
                    .body(JsonNode.class);
        } catch (RestClientException e) {
            throw new BusinessException(ErrorCode.AI_FEEDBACK_FAILED);
        }

        return parse(response);
    }

    private Map<String, Object> requestBody(String question, String answer, int charLimit, String targetPosition) {
        String position = (targetPosition == null || targetPosition.isBlank()) ? "미지정" : targetPosition;
        String userText = """
                [질문]
                %s
                [답변]
                %s
                [글자 수 제한] %d
                [지원 직무] %s
                """.formatted(question, answer, charLimit, position);

        return Map.of(
                "systemInstruction", Map.of("parts", List.of(Map.of("text", SYSTEM_INSTRUCTION))),
                "contents", List.of(Map.of("parts", List.of(Map.of("text", userText)))),
                "generationConfig", Map.of(
                        "responseMimeType", "application/json",
                        "responseSchema", responseSchema(),
                        "temperature", 0.4));
    }

    private Map<String, Object> responseSchema() {
        Map<String, Object> comment = Map.of(
                "type", "OBJECT",
                "properties", Map.of(
                        "quote", Map.of("type", "STRING"),
                        "category", Map.of("type", "STRING",
                                "enum", List.of("직무적합성", "구체성", "논리성", "가독성", "맞춤법")),
                        "severity", Map.of("type", "STRING",
                                "enum", List.of("WARNING", "SUGGESTION", "INFO")),
                        "message", Map.of("type", "STRING"),
                        "suggestion", Map.of("type", "STRING")),
                "required", List.of("quote", "category", "severity", "message"));

        return Map.of(
                "type", "OBJECT",
                "properties", Map.of(
                        "summary", Map.of("type", "STRING"),
                        "comments", Map.of("type", "ARRAY", "items", comment)),
                "required", List.of("summary", "comments"));
    }

    private AiFeedback parse(JsonNode response) {
        if (response == null) {
            throw new BusinessException(ErrorCode.AI_FEEDBACK_FAILED);
        }
        // responseMimeType=application/json 이라 parts[0].text 가 JSON 문자열이다.
        JsonNode textNode = response.path("candidates").path(0).path("content").path("parts").path(0).path("text");
        if (!textNode.isString()) {
            throw new BusinessException(ErrorCode.AI_FEEDBACK_FAILED);
        }
        try {
            return toPlainText(objectMapper.readValue(textNode.asString(), AiFeedback.class));
        } catch (RuntimeException e) {
            throw new BusinessException(ErrorCode.AI_FEEDBACK_FAILED);
        }
    }

    /**
     * 사람이 읽는 칸에서만 마크다운 기호를 벗긴다.
     *
     * <p><b>quote 는 건드리지 않는다.</b> 답변 본문에서 그 문자열을 찾아 하이라이트 구간을
     * 잡기 때문에(CoverLetterService 의 indexOf), 한 글자만 달라져도 위치를 못 찾는다.
     */
    private static AiFeedback toPlainText(AiFeedback feedback) {
        List<AiFeedback.AiComment> comments = feedback.comments() == null ? List.of()
                : feedback.comments().stream()
                        .map(c -> new AiFeedback.AiComment(
                                c.quote(),
                                c.category(),
                                c.severity(),
                                PlainText.of(c.message()),
                                PlainText.of(c.suggestion())))
                        .toList();
        return new AiFeedback(PlainText.of(feedback.summary()), comments);
    }
}

package com.ssafy.companyanalysis.agent.ai;

import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import tools.jackson.databind.JsonNode;

import java.util.List;
import java.util.Map;

/**
 * 글쓰기 담당 API 호출({@code POST /writing/internal/messages}).
 *
 * <p>문항 하나와 사용자가 승인한 초안 하나를 기준으로 첨삭한다. 돌아온 수정문은 제안일
 * 뿐이므로 초안으로 자동 승격하지 않는다 — 저장은 사용자가 수락한 뒤에 한다.
 */
@Component
public class WritingCoachingClient {

    private static final int MAX_CONVERSATION = 20;
    private static final int MAX_MESSAGE = 10_000;
    private static final int MAX_QUESTION = 500;
    private static final int MAX_DRAFT = 50_000;
    private static final int MAX_CHAR_LIMIT = 50_000;
    private static final String AGENT_NAME = "글쓰기 담당";

    private final RestClient agentAiRestClient;
    private final AgentAiProperties properties;

    public WritingCoachingClient(RestClient agentAiRestClient, AgentAiProperties properties) {
        this.agentAiRestClient = agentAiRestClient;
        this.properties = properties;
    }

    /**
     * @param charLimit 문항의 글자 수 제한. 0 이하면 초안 길이를 대신 쓴다 — AI 쪽이 1 이상만 받는다
     */
    public Revision revise(String message,
                           String question,
                           String draft,
                           int charLimit,
                           List<PositionAnalysisClient.Turn> conversation) {
        if (!properties.hasBaseUrl()) {
            throw new BusinessException(ErrorCode.AI_UNAVAILABLE,
                    AGENT_NAME + " AI 서버 주소가 설정되지 않았습니다.");
        }
        if (draft == null || draft.isBlank()) {
            throw new BusinessException(ErrorCode.AI_FAILED, "검토할 초안이 비어 있습니다.");
        }

        String body = trim(draft, MAX_DRAFT);
        Map<String, Object> request = Map.of(
                "message", trim(message, MAX_MESSAGE),
                "question", trim(question, MAX_QUESTION),
                "draft", body,
                "char_limit", boundedCharLimit(charLimit, body),
                "feedback", List.of(),
                "conversation", conversation.stream()
                        .limit(MAX_CONVERSATION)
                        .map(turn -> Map.of(
                                "message_id", turn.messageId(),
                                "role", turn.role(),
                                "content", turn.content()))
                        .toList());

        JsonNode response = AgentAiCall.post(
                agentAiRestClient, "/writing/internal/messages", request, AGENT_NAME);

        String status = response.path("status").asString("");
        String reply = response.path("message").asString("");
        if (reply.isBlank()) {
            throw new BusinessException(ErrorCode.AI_FAILED, AGENT_NAME + " 이 빈 응답을 돌려줬습니다.");
        }
        JsonNode revision = response.path("revision");
        String revisedText = revision.isObject() ? revision.path("revised_text").asString("") : null;
        return new Revision(status, reply, revisedText == null || revisedText.isBlank() ? null : revisedText);
    }

    /** 글자 수 제한을 안 적어 둔 문항이 있다. 0 을 그대로 보내면 422 가 돌아온다. */
    private static int boundedCharLimit(int charLimit, String draft) {
        int limit = charLimit > 0 ? charLimit : draft.length();
        return Math.min(Math.max(limit, 1), MAX_CHAR_LIMIT);
    }

    private static String trim(String value, int limit) {
        String text = value == null ? "" : value;
        return text.length() > limit ? text.substring(0, limit) : text;
    }

    /**
     * @param status      {@code REVISED} · {@code ANSWERED} · {@code CLARIFICATION_REQUIRED}
     * @param message     화면에 띄울 문구
     * @param revisedText 제안 수정문. {@code REVISED} 가 아니면 null
     */
    public record Revision(String status, String message, String revisedText) {
    }
}

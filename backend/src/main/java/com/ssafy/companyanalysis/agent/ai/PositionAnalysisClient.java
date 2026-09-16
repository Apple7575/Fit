package com.ssafy.companyanalysis.agent.ai;

import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import tools.jackson.databind.JsonNode;

import java.util.List;
import java.util.Map;

/**
 * 포지션 담당 API 호출({@code POST /position/internal/analyses}).
 *
 * <p>합격 가능성을 매기는 API 가 아니다. 사용자가 쓴 경험에 상황·역할·행동·검증·결과가
 * 이어지는지 보고 후속 질문을 만든다.
 *
 * <p>화면에 띄울 {@code message} 만 돌려준다. 근거와 후속 질문이 담긴 {@code analysis} 는
 * 저장할 자리를 아직 정하지 않아 받지 않는다(S15P21A504-141).
 */
@Component
public class PositionAnalysisClient {

    /** AI 쪽이 이 값만 받는다. */
    private static final String RUBRIC_ID = "experience-depth-v1";
    private static final int MAX_REQUIREMENTS = 20;
    private static final int MAX_DOCUMENTS = 21;
    private static final int MAX_CONVERSATION = 20;
    private static final int MAX_POSITION_NAME = 200;
    private static final String AGENT_NAME = "포지션 담당";

    private final RestClient agentAiRestClient;
    private final AgentAiProperties properties;

    public PositionAnalysisClient(RestClient agentAiRestClient, AgentAiProperties properties) {
        this.agentAiRestClient = agentAiRestClient;
        this.properties = properties;
    }

    /**
     * @param documents 분석의 사실 근거. 자소서 답변이 여기 들어간다
     * @param conversation 대화 흐름 문맥일 뿐 근거로 쓰이지 않는다
     * @return 화면에 그대로 띄울 한 문단
     */
    public String analyze(String positionName,
                          List<String> priorityRequirements,
                          List<Document> documents,
                          List<Turn> conversation) {
        if (!properties.hasBaseUrl()) {
            throw new BusinessException(ErrorCode.AI_UNAVAILABLE,
                    AGENT_NAME + " AI 서버 주소가 설정되지 않았습니다.");
        }
        if (documents.isEmpty()) {
            throw new BusinessException(ErrorCode.AI_FAILED, "검토할 자소서 답변이 없습니다.");
        }

        Map<String, Object> body = Map.of(
                "rubric_id", RUBRIC_ID,
                "position_context", Map.of(
                        "position_name", trim(positionName, MAX_POSITION_NAME),
                        "priority_requirements", priorityRequirements.stream()
                                .limit(MAX_REQUIREMENTS)
                                .toList()),
                "documents", documents.stream()
                        .limit(MAX_DOCUMENTS)
                        .map(document -> Map.of(
                                "document_id", document.documentId(),
                                "document_type", document.type(),
                                "text", document.text()))
                        .toList(),
                "conversation", conversation.stream()
                        .limit(MAX_CONVERSATION)
                        .map(turn -> Map.of(
                                "message_id", turn.messageId(),
                                "role", turn.role(),
                                "content", turn.content()))
                        .toList());

        JsonNode response = AgentAiCall.post(
                agentAiRestClient, "/position/internal/analyses", body, AGENT_NAME);
        String message = response.path("message").asString("");
        if (message.isBlank()) {
            throw new BusinessException(ErrorCode.AI_FAILED, AGENT_NAME + " 이 빈 응답을 돌려줬습니다.");
        }
        return message;
    }

    private static String trim(String value, int limit) {
        return value.length() > limit ? value.substring(0, limit) : value;
    }

    /** @param type {@code SELF_INTRO} 또는 {@code EXPERIENCE} */
    public record Document(String documentId, String type, String text) {
    }

    /** @param role {@code USER} 또는 {@code ASSISTANT} */
    public record Turn(String messageId, String role, String content) {
    }
}

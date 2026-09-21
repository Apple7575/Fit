package com.ssafy.companyanalysis.agent.ai;

import com.ssafy.companyanalysis.agent.domain.Evidence;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import tools.jackson.databind.JsonNode;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 총괄 담당 API 호출({@code POST /supervisor/internal/runs}).
 *
 * <p>한 번의 호출로 채용공고·포지션·글쓰기·뉴스 담당 중 필요한 것을 AI 쪽이 골라 돌리고
 * 결과를 종합해 준다. 어떤 담당이 돌 수 있는지는 {@code agent_contexts} 에 무엇을 넣었는지로
 * 정해지고, 그중 무엇을 실제로 돌릴지는 총괄의 계획이 정한다.
 *
 * <p>담당 하나만 돌릴 때는 {@code lead} 를 지정한다. 계획 단계를 건너뛰어 모델 호출이 한 번
 * 줄고, 위임·근거 기록은 총괄 경로와 똑같이 동작한다.
 *
 * <p>응답에 모르는 필드가 늘어날 수 있다는 것이 명세에 못박혀 있다. 그래서 응답을 통째로
 * 매핑하지 않고 {@link JsonNode} 에서 쓸 것만 꺼낸다.
 */
@Component
public class SupervisorClient {

    private static final String RUN_PATH = "/supervisor/internal/runs";
    private static final String AGENT_NAME = "총괄";
    private static final int MAX_INSTRUCTION = 10_000;
    private static final int MAX_DOCUMENTS = 21;
    private static final int MAX_DOCUMENT_TEXT = 50_000;
    private static final int MAX_CONVERSATION = 20;
    private static final int MAX_CONVERSATION_CONTENT = 10_000;

    private final RestClient supervisorAiRestClient;
    private final AgentAiProperties properties;

    public SupervisorClient(RestClient supervisorAiRestClient, AgentAiProperties properties) {
        this.supervisorAiRestClient = supervisorAiRestClient;
        this.properties = properties;
    }

    /**
     * @param agentContexts 담당별 컨텍스트. 여기 없는 담당은 총괄이 고르지 않는다
     * @param lead          담당 직접 호출. 총괄에게 맡기려면 null
     * @param runEveryAgent 실행 가능한 담당을 전부 돌린다. 첫 자동 검토에 쓴다
     */
    public Run run(String instruction,
                   List<Document> documents,
                   List<Turn> conversation,
                   Map<String, Object> agentContexts,
                   String lead,
                   boolean runEveryAgent) {
        if (!properties.hasBaseUrl()) {
            throw new BusinessException(ErrorCode.AI_UNAVAILABLE,
                    AGENT_NAME + " AI 서버 주소가 설정되지 않았습니다.");
        }
        if (agentContexts.isEmpty()) {
            throw new BusinessException(ErrorCode.AI_FAILED, "실행할 담당이 없습니다.");
        }

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("instruction", trim(instruction, MAX_INSTRUCTION));
        body.put("documents", documents.stream()
                .limit(MAX_DOCUMENTS)
                .map(document -> Map.of(
                        "document_id", document.documentId(),
                        "document_type", document.documentType(),
                        "text", trim(document.text(), MAX_DOCUMENT_TEXT)))
                .toList());
        body.put("conversation", conversation.stream()
                .limit(MAX_CONVERSATION)
                .map(turn -> Map.of(
                        "message_id", turn.messageId(),
                        "role", turn.role(),
                        "content", trim(turn.content(), MAX_CONVERSATION_CONTENT)))
                .toList());
        body.put("agent_contexts", agentContexts);
        // 명세가 모르는 필드를 422 로 거른다. 총괄에게 맡길 때는 키 자체를 넣지 않는다.
        if (lead != null) {
            body.put("lead", lead);
        }
        // 자소서를 받아 방을 한 바퀴 도는 첫 검토는 고를 질문이 없다. 총괄이 골라내면 담당
        // 대부분이 "이 관점은 필요 없다" 로 남아 미리 봐 두는 의미가 사라진다.
        if (runEveryAgent) {
            body.put("agent_selection", "all");
        }

        JsonNode response = AgentAiCall.post(supervisorAiRestClient, RUN_PATH, body, AGENT_NAME);
        return toRun(response);
    }

    private static Run toRun(JsonNode response) {
        List<AgentResult> results = new ArrayList<>();
        for (JsonNode node : response.path("agent_results")) {
            String agent = node.path("agent").asString("");
            if (agent.isBlank()) {
                continue;
            }
            results.add(new AgentResult(
                    agent,
                    node.path("status").asString(""),
                    AgentResultText.of(agent, node.path("result")),
                    nullable(node, "error"),
                    EvidenceMapper.fromArray(node.path("evidence"))));
        }
        return new Run(
                response.path("status").asString(""),
                response.path("message").asString(""),
                nullable(response.path("plan"), "reason"),
                List.copyOf(results),
                EvidenceMapper.fromArray(response.path("evidence")));
    }

    private static String trim(String value, int limit) {
        String text = value == null ? "" : value;
        return text.length() > limit ? text.substring(0, limit) : text;
    }

    private static String nullable(JsonNode node, String field) {
        String value = node.path(field).asString("");
        return value.isBlank() ? null : value;
    }

    /** @param documentType {@code SELF_INTRO} · {@code EXPERIENCE} · {@code RESUME} · {@code PORTFOLIO} */
    public record Document(String documentId, String documentType, String text) {
    }

    /** @param role {@code USER} 또는 {@code ASSISTANT} */
    public record Turn(String messageId, String role, String content) {
    }

    /**
     * @param status       {@code SUCCESS}(전부 성공) 또는 {@code PARTIAL}(일부 실패)
     * @param message      총괄이 종합한 문구
     * @param planReason   담당을 그렇게 고른 이유. 담당 직접 호출이면 없다
     * @param agentResults 실제로 돈 담당만 들어온다. 고르지 않은 담당은 아예 빠진다
     * @param evidence     담당들이 쓴 근거의 합집합
     */
    public record Run(String status, String message, String planReason,
                      List<AgentResult> agentResults, List<Evidence> evidence) {
    }

    /**
     * @param status  {@code SUCCESS} 또는 {@code FAILED}
     * @param message 화면에 띄울 글. 실패하면 비어 있다
     * @param error   실패 사유. 성공이면 null
     */
    public record AgentResult(String agent, String status, String message, String error,
                              List<Evidence> evidence) {

        public boolean succeeded() {
            return "SUCCESS".equals(status);
        }
    }
}

package com.ssafy.companyanalysis.agent.ai;

import com.ssafy.companyanalysis.agent.domain.Evidence;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import tools.jackson.databind.JsonNode;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 기업 분석 담당 API 호출({@code POST /company/internal/messages}).
 *
 * <p>공시(사업보고서·확정 지표)만 근거로 답한다. 뉴스는 근거에 넣지 않으며, 대화 중 뉴스가
 * 필요하다고 판단하면 답 대신 {@code needs} 를 돌려준다 — 담당 방에는 뉴스 담당이 없으므로
 * 그 요청은 총괄 논의 방에서만 처리된다.
 *
 * <p>무상태다. 대화는 백엔드가 방에 보관하고 매 호출마다 {@code conversation} 으로 넘긴다.
 * AI 쪽 {@code /internal/chat} 은 대화를 따로 저장하는 별개 경로로, 담당 방은 쓰지 않는다.
 *
 * <p>담당이 기업 하나뿐일 때 여기로 온다. 다른 담당과 같이 돌 때는 총괄이 대신 부른다
 * ({@link SupervisorClient}). 기업 담당만 필요한데 총괄을 거치면 왕복이 하나 더 붙는다.
 */
@Component
public class CompanyAnalysisClient {

    private static final String PATH = "/company/internal/messages";
    private static final String AGENT_NAME = "기업 RAG 담당";
    private static final int MAX_MESSAGE = 4_000;
    private static final int MAX_CONVERSATION = 20;
    private static final int MAX_CONVERSATION_CONTENT = 4_000;

    /** 서술 블록이 아직 안 붙은 리포트로 답한 경우. 실패가 아니라서 화면에 그대로 알린다. */
    private static final String DETERMINISTIC = "DETERMINISTIC";
    private static final String ENRICHING_NOTICE =
            "\n\n(아직 이 기업의 서술 분석을 만드는 중입니다. 잠시 뒤 다시 물어보면 더 자세히 답할 수 있습니다.)";

    private final RestClient supervisorAiRestClient;
    private final AgentAiProperties properties;

    public CompanyAnalysisClient(RestClient supervisorAiRestClient, AgentAiProperties properties) {
        this.supervisorAiRestClient = supervisorAiRestClient;
        this.properties = properties;
    }

    public Answer answer(String message,
                         String corpCode,
                         String jobContextId,
                         List<SupervisorClient.Turn> conversation) {
        if (!properties.hasBaseUrl()) {
            throw new BusinessException(ErrorCode.AI_UNAVAILABLE,
                    AGENT_NAME + " AI 서버 주소가 설정되지 않았습니다.");
        }

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("corp_code", corpCode);
        body.put("message", trim(message, MAX_MESSAGE));
        body.put("conversation", conversation.stream()
                .limit(MAX_CONVERSATION)
                .map(turn -> Map.of(
                        "message_id", turn.messageId(),
                        "role", turn.role(),
                        "content", trim(turn.content(), MAX_CONVERSATION_CONTENT)))
                .toList());
        // 명세가 모르는 필드를 422 로 거른다. 공고가 없으면 키 자체를 넣지 않는다.
        if (jobContextId != null && !jobContextId.isBlank()) {
            body.put("job_context_id", jobContextId);
        }

        JsonNode response = AgentAiCall.post(supervisorAiRestClient, PATH, body, AGENT_NAME);
        String answer = response.path("message").asString("");
        if (answer.isBlank()) {
            throw new BusinessException(ErrorCode.AI_FAILED, AGENT_NAME + " 이 빈 응답을 돌려줬습니다.");
        }
        if (DETERMINISTIC.equals(response.path("report_stage").asString(""))) {
            answer = answer + ENRICHING_NOTICE;
        }
        return new Answer(answer, EvidenceMapper.fromCompanyCitations(
                response.path("citations"), response.path("corp_name").asString("")));
    }

    private static String trim(String value, int limit) {
        String text = value == null ? "" : value;
        return text.length() > limit ? text.substring(0, limit) : text;
    }

    public record Answer(String message, List<Evidence> evidence) {
    }
}

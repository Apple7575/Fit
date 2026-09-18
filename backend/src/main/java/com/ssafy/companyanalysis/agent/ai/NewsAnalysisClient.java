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
 * 뉴스 담당 API 호출({@code POST /news/internal/analyses}).
 *
 * <p>기업·산업·직무 변화를 저장된 기사 근거에 기대어 분석한다. 인용하지 않은 서술은 만들지
 * 않으므로, 볼 기사가 없으면 빈 손으로 돌아온다 — 그것도 정상 응답이다.
 *
 * <p>돌릴 담당이 뉴스 하나뿐일 때만 여기로 온다. 다른 담당과 같이 돌 때는 총괄이 대신 부른다
 * ({@link SupervisorClient}). 뉴스만 필요한데 총괄을 거치면 계획·종합 모델 호출이 공짜로 두 번
 * 더 붙는다.
 */
@Component
public class NewsAnalysisClient {

    private static final String PATH = "/news/internal/analyses";
    private static final String AGENT_NAME = "뉴스 담당";
    private static final int MAX_INSTRUCTION = 10_000;
    private static final int MAX_CONVERSATION = 20;
    private static final int MAX_CONVERSATION_CONTENT = 10_000;

    /** 근거가 모자라 신호를 못 만든 경우. 실패가 아니라서 화면에 그대로 알린다. */
    private static final String INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE";
    private static final String NO_EVIDENCE_MESSAGE =
            "근거로 삼을 기사를 찾지 못했습니다. 최근 기사가 쌓이면 다시 물어봐 주세요.";

    private final RestClient supervisorAiRestClient;
    private final AgentAiProperties properties;

    public NewsAnalysisClient(RestClient supervisorAiRestClient, AgentAiProperties properties) {
        this.supervisorAiRestClient = supervisorAiRestClient;
        this.properties = properties;
    }

    public Analysis analyze(String instruction,
                            String jobContextId,
                            String corpCode,
                            List<SupervisorClient.Turn> conversation) {
        if (!properties.hasBaseUrl()) {
            throw new BusinessException(ErrorCode.AI_UNAVAILABLE,
                    AGENT_NAME + " AI 서버 주소가 설정되지 않았습니다.");
        }

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("instruction", trim(instruction, MAX_INSTRUCTION));
        body.put("job_context_id", jobContextId);
        body.put("corp_code", corpCode);
        body.put("conversation", conversation.stream()
                .limit(MAX_CONVERSATION)
                .map(turn -> Map.of(
                        "message_id", turn.messageId(),
                        "role", turn.role(),
                        "content", trim(turn.content(), MAX_CONVERSATION_CONTENT)))
                .toList());

        JsonNode response = AgentAiCall.post(supervisorAiRestClient, PATH, body, AGENT_NAME);
        JsonNode analysis = response.path("analysis");
        String message = response.path("message").asString("");
        if (INSUFFICIENT_EVIDENCE.equals(analysis.path("analysis_status").asString(""))
                && message.isBlank()) {
            message = NO_EVIDENCE_MESSAGE;
        }
        if (message.isBlank()) {
            throw new BusinessException(ErrorCode.AI_FAILED, AGENT_NAME + " 이 빈 응답을 돌려줬습니다.");
        }
        return new Analysis(message, EvidenceMapper.fromNewsSignals(analysis));
    }

    private static String trim(String value, int limit) {
        String text = value == null ? "" : value;
        return text.length() > limit ? text.substring(0, limit) : text;
    }

    public record Analysis(String message, List<Evidence> evidence) {
    }
}

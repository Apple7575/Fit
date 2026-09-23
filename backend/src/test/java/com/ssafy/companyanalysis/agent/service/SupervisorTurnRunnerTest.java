package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.ai.NewsAnalysisClient;
import com.ssafy.companyanalysis.agent.ai.SupervisorClient;
import com.ssafy.companyanalysis.agent.domain.Evidence;
import com.ssafy.companyanalysis.agent.domain.Message;
import com.ssafy.companyanalysis.agent.domain.MessageStatus;
import com.ssafy.companyanalysis.agent.repository.MessageRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.mockito.Mockito;

import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;

class SupervisorTurnRunnerTest {

    private static final Long TURN_ID = 100L;

    private MessageRepository messageRepository;
    private SupervisorClient supervisorClient;
    private NewsAnalysisClient newsClient;
    private SupervisorTurnRunner runner;
    private final AtomicLong seq = new AtomicLong(200);

    @BeforeEach
    void setUp() {
        messageRepository = Mockito.mock(MessageRepository.class);
        supervisorClient = Mockito.mock(SupervisorClient.class);
        newsClient = Mockito.mock(NewsAnalysisClient.class);
        runner = new SupervisorTurnRunner(messageRepository, supervisorClient, newsClient);
    }

    @Test
    @DisplayName("담당별 결과를 자기 자리에 넣고 총괄 자리에는 종합 문구를 남긴다")
    void everyAgentResultLandsInItsOwnSlot() {
        Map<String, Message> slots = slots("jd", "writing", "supervisor");
        given(supervisorClient.run(anyString(), any(), any(), any(), any(), anyBoolean()))
                .willReturn(new SupervisorClient.Run("SUCCESS", "지원동기 문단을 먼저 고치세요.", "첨삭 요청",
                        List.of(success("jd", "공고가 요구하는 항목이 빠졌습니다."),
                                success("writing", "첫 문장을 앞으로 올렸습니다.")),
                        List.of(evidence("삼성전자, AI 인프라 투자 확대"))));

        runner.run(TURN_ID, context());

        assertThat(slots.get("jd").getContent()).isEqualTo("공고가 요구하는 항목이 빠졌습니다.");
        assertThat(slots.get("writing").getContent()).isEqualTo("첫 문장을 앞으로 올렸습니다.");
        Message supervisor = slots.get("supervisor");
        assertThat(supervisor.getStatus()).isEqualTo(MessageStatus.DONE);
        assertThat(supervisor.getContent()).isEqualTo("지원동기 문단을 먼저 고치세요.");
        assertThat(supervisor.getEvidences()).hasSize(1);
        // 화면이 근거 칩으로 연결할 수 있도록 종합에 쓴 자리를 남긴다.
        assertThat(supervisor.getBasedOn())
                .containsExactly(slots.get("jd").getId(), slots.get("writing").getId());
    }

    @Test
    @DisplayName("총괄이 고르지 않은 담당은 실패가 아니라 넘어갔다고 남긴다")
    void agentsTheSupervisorDidNotPickAreNotFailures() {
        Map<String, Message> slots = slots("jd", "writing", "supervisor");
        given(supervisorClient.run(anyString(), any(), any(), any(), any(), anyBoolean()))
                .willReturn(new SupervisorClient.Run("SUCCESS", "첫 문장을 앞으로 올렸습니다.", "첨삭만 필요",
                        List.of(success("writing", "첫 문장을 앞으로 올렸습니다.")), List.of()));

        runner.run(TURN_ID, context());

        Message jd = slots.get("jd");
        assertThat(jd.getStatus()).isEqualTo(MessageStatus.DONE);
        assertThat(jd.getContent()).contains("필요하지 않다고 보고 넘어갔습니다");
    }

    @Test
    @DisplayName("담당 하나가 실패해도 나머지 자리와 총괄은 그대로 채워진다")
    void oneFailedAgentDoesNotSinkTheTurn() {
        Map<String, Message> slots = slots("news", "writing", "supervisor");
        given(supervisorClient.run(anyString(), any(), any(), any(), any(), anyBoolean()))
                .willReturn(new SupervisorClient.Run("PARTIAL", "뉴스 근거 없이 문장만 다듬었습니다.", null,
                        List.of(new SupervisorClient.AgentResult("news", "FAILED", "",
                                        "기사 저장소를 사용할 수 없습니다.", List.of()),
                                success("writing", "첫 문장을 앞으로 올렸습니다.")),
                        List.of()));

        runner.run(TURN_ID, context());

        assertThat(slots.get("news").getStatus()).isEqualTo(MessageStatus.FAILED);
        assertThat(slots.get("news").getError()).isEqualTo("기사 저장소를 사용할 수 없습니다.");
        assertThat(slots.get("supervisor").getStatus()).isEqualTo(MessageStatus.DONE);
        assertThat(slots.get("supervisor").getBasedOn())
                .containsExactly(slots.get("writing").getId());
    }

    @Test
    @DisplayName("어느 담당이든 JSON 문자열을 보내면 말풍선에는 안전한 안내만 남긴다")
    void jsonMessagesNeverReachAgentBubbles() {
        Map<String, Message> slots = slots("jd", "supervisor");
        given(supervisorClient.run(anyString(), any(), any(), any(), any(), anyBoolean()))
                .willReturn(new SupervisorClient.Run("SUCCESS", "{\"internal\":true}", null,
                        List.of(success("jd", "{\"score\":72}")), List.of()));

        runner.run(TURN_ID, context());

        assertThat(slots.get("jd").getContent())
                .isEqualTo("분석은 완료됐지만 읽을 수 있는 요약을 만들지 못했습니다. 다시 요청해 주세요.");
        assertThat(slots.get("supervisor").getContent())
                .isEqualTo("종합은 완료됐지만 읽을 수 있는 요약을 만들지 못했습니다. 다시 요청해 주세요.");
    }

    @Test
    @DisplayName("담당과 총괄이 마크다운을 써도 말풍선에는 평문으로 남긴다 — 화면이 기호를 그리지 않는다")
    void markdownIsStoredAsPlainText() {
        Map<String, Message> slots = slots("jd", "supervisor");
        given(supervisorClient.run(anyString(), any(), any(), any(), any(), anyBoolean()))
                .willReturn(new SupervisorClient.Run("SUCCESS", "## 종합\n**먼저** 고칠 것", null,
                        List.of(success("jd", "- **자격요건** 누락")), List.of()));

        runner.run(TURN_ID, context());

        assertThat(slots.get("jd").getContent()).isEqualTo("• 자격요건 누락");
        assertThat(slots.get("supervisor").getContent()).isEqualTo("종합\n먼저 고칠 것");
    }

    @Test
    @DisplayName("30턴 동안 모든 담당의 JSON 원문은 어떤 말풍선에도 저장되지 않는다")
    void thirtyTurnsNeverPersistRawJsonFromAnyAgent() {
        List<String> agents = List.of("jd", "position", "writing", "news", "company");

        for (int turn = 1; turn <= 30; turn++) {
            int currentTurn = turn;
            Map<String, Message> slots = slots("jd", "position", "writing", "news", "company", "supervisor");
            given(messageRepository.findByParentMessageIdOrderByIdAsc(TURN_ID + currentTurn))
                    .willReturn(new ArrayList<>(slots.values()));
            List<SupervisorClient.AgentResult> results = agents.stream()
                    .map(agent -> success(agent, "{\"agent\":\"" + agent + "\",\"turn\":" + currentTurn + "}"))
                    .toList();
            given(supervisorClient.run(anyString(), any(), any(), any(), any(), anyBoolean()))
                    .willReturn(new SupervisorClient.Run("SUCCESS", "{\"turn\":" + currentTurn + "}", null,
                            results, List.of()));

            runner.run(TURN_ID + currentTurn, context());

            for (String agent : agents) {
                assertThat(slots.get(agent).getContent())
                        .isEqualTo("분석은 완료됐지만 읽을 수 있는 요약을 만들지 못했습니다. 다시 요청해 주세요.");
            }
            assertThat(slots.get("supervisor").getContent())
                    .isEqualTo("종합은 완료됐지만 읽을 수 있는 요약을 만들지 못했습니다. 다시 요청해 주세요.");
        }
    }

    @Test
    @DisplayName("GMS 제한 초과 담당은 내부 코드 대신 재시도 안내를 남긴다")
    void rateLimitedAgentGetsRetryMessage() {
        Map<String, Message> slots = slots("news", "writing", "supervisor");
        given(supervisorClient.run(anyString(), any(), any(), any(), any(), anyBoolean()))
                .willReturn(new SupervisorClient.Run("PARTIAL", "문장 검토는 완료했습니다.", null,
                        List.of(new SupervisorClient.AgentResult("news", "FAILED", "",
                                        "GMS_RATE_LIMITED", List.of()),
                                success("writing", "첫 문장을 앞으로 올렸습니다.")),
                        List.of()));

        runner.run(TURN_ID, context());

        assertThat(slots.get("news").getStatus()).isEqualTo(MessageStatus.FAILED);
        assertThat(slots.get("news").getError())
                .isEqualTo(ErrorCode.AI_RATE_LIMITED.getDefaultMessage());
    }

    @Test
    @DisplayName("총괄 호출 자체가 막히면 이 턴의 자리를 모두 실패로 닫는다 — 영원히 도는 자리를 두지 않는다")
    void everySlotIsClosedWhenTheCallItselfFails() {
        Map<String, Message> slots = slots("jd", "writing", "supervisor");
        willThrow(new BusinessException(ErrorCode.AI_UNAVAILABLE,
                "총괄 AI 서버가 아직 모델에 연결되지 않았습니다."))
                .given(supervisorClient).run(anyString(), any(), any(), any(), any(), anyBoolean());

        runner.run(TURN_ID, context());

        assertThat(slots.values()).allSatisfy(slot -> {
            assertThat(slot.getStatus()).isEqualTo(MessageStatus.FAILED);
            assertThat(slot.getError()).contains("아직 모델에 연결되지 않았습니다");
        });
    }

    @Test
    @DisplayName("돌릴 담당이 뉴스뿐이면 뉴스 API 를 바로 부른다")
    void newsOnlyTurnCallsTheNewsApiDirectly() {
        Map<String, Message> slots = slots("news");
        given(newsClient.analyze(anyString(), anyString(), anyString(), any()))
                .willReturn(new NewsAnalysisClient.Analysis("최근 생산능력 확대가 눈에 띕니다.",
                        List.of(evidence("삼성전자, 생산능력 확대 발표"))));

        runner.run(TURN_ID, newsOnlyContext());

        ArgumentCaptor<String> corpCode = ArgumentCaptor.forClass(String.class);
        Mockito.verify(newsClient)
                .analyze(anyString(), anyString(), corpCode.capture(), any());
        Mockito.verifyNoInteractions(supervisorClient);
        assertThat(corpCode.getValue()).isEqualTo("00126380");
        assertThat(slots.get("news").getContent()).isEqualTo("최근 생산능력 확대가 눈에 띕니다.");
        assertThat(slots.get("news").getEvidences()).hasSize(1);
    }

    private Map<String, Message> slots(String... agentKeys) {
        Map<String, Message> slots = new java.util.LinkedHashMap<>();
        List<Message> saved = new ArrayList<>();
        for (String key : agentKeys) {
            Message message = withId(Message.pendingAgent(9L, TURN_ID, key), seq.incrementAndGet());
            slots.put(key, message);
            saved.add(message);
        }
        given(messageRepository.findByParentMessageIdOrderByIdAsc(TURN_ID)).willReturn(saved);
        return slots;
    }

    private static SupervisorClient.AgentResult success(String agent, String message) {
        return new SupervisorClient.AgentResult(agent, "SUCCESS", message, null, List.of());
    }

    private static Evidence evidence(String title) {
        return new Evidence("NEWS_ARTICLE", title, 2026, null, "요약", "https://news.example.test/1");
    }

    /** 담당을 전부 고른 방(총괄 논의). 설정은 뉴스 담당만 채워 둔다. */
    private static TurnContext context() {
        Map<String, Map<String, Object>> everyAgent = new LinkedHashMap<>();
        everyAgent.put("jd", Map.of());
        everyAgent.put("company", Map.of());
        everyAgent.put("position", Map.of());
        everyAgent.put("news", Map.of("corpCodes", List.of("00126380")));
        everyAgent.put("writing", Map.of());
        return new TurnContext(
                List.of(new TurnContext.CoverLetterPart(1, "지원동기", "저는 API 를 만들었습니다.", 1000)),
                "봐줘", "ctx-1", "백엔드", List.of(), everyAgent, false);
    }

    /** 아직 아무 문항도 쓰지 않은 방. 보낼 문서가 없어 뉴스 담당만 돌 수 있다. */
    private static TurnContext newsOnlyContext() {
        return new TurnContext(
                List.of(new TurnContext.CoverLetterPart(1, "지원동기", "   ", 1000)),
                "요즘 이 회사 어때?", "ctx-1", null, List.of(),
                Map.of("news", Map.of("corpCodes", List.of("00126380"))), false);
    }

    private static Message withId(Message message, long id) {
        try {
            Field field = Message.class.getDeclaredField("id");
            field.setAccessible(true);
            field.set(message, id);
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException(e);
        }
        return message;
    }
}

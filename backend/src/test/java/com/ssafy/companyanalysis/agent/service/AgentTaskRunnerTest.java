package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.domain.AgentType;
import com.ssafy.companyanalysis.agent.domain.Message;
import com.ssafy.companyanalysis.agent.domain.MessageStatus;
import com.ssafy.companyanalysis.agent.repository.MessageRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;

/**
 * 백엔드에 남은 담당은 기업 RAG 하나뿐이다. 나머지는 AI 총괄이 맡는다
 * ({@link SupervisorTurnRunnerTest}).
 */
class AgentTaskRunnerTest {

    private static final Long MESSAGE_ID = 31L;

    private MessageRepository messageRepository;
    private AgentTaskRunner runner;

    @BeforeEach
    void setUp() {
        messageRepository = Mockito.mock(MessageRepository.class);
        runner = new AgentTaskRunner(messageRepository);
    }

    @Test
    @DisplayName("기업 RAG 담당은 볼 Vector DB 가 없어 자기 자리에서 실패한다")
    void companyAgentFailsUntilTheVectorDbExists() {
        Message message = slotOf(AgentType.COMPANY);

        runner.run(MESSAGE_ID, contextOf(AgentType.COMPANY, Map.of("corpCodes", List.of("00126380"))));

        assertThat(message.getStatus()).isEqualTo(MessageStatus.FAILED);
        assertThat(message.getError()).contains("볼 자료가 아직 준비되지 않았습니다");
    }

    @Test
    @DisplayName("기업을 고르지 않았으면 설정을 채우라고 알린다")
    void companyAgentAsksForItsConfigFirst() {
        Message message = slotOf(AgentType.COMPANY);

        runner.run(MESSAGE_ID, contextOf(AgentType.COMPANY, Map.of()));

        assertThat(message.getStatus()).isEqualTo(MessageStatus.FAILED);
        assertThat(message.getError()).contains("설정을 먼저 채워 주세요");
    }

    @Test
    @DisplayName("AI 총괄이 맡은 담당이 잘못 흘러들어도 그 자리만 실패한다")
    void agentsOwnedByTheSupervisorDoNotRunHere() {
        Message message = slotOf(AgentType.WRITING);

        runner.run(MESSAGE_ID, contextOf(AgentType.WRITING, Map.of()));

        assertThat(message.getStatus()).isEqualTo(MessageStatus.FAILED);
        assertThat(message.getError()).isEqualTo("지금은 이 에이전트를 쓸 수 없습니다.");
    }

    private Message slotOf(AgentType type) {
        Message message = Message.pendingAgent(9L, 8L, type.key());
        given(messageRepository.findById(MESSAGE_ID)).willReturn(Optional.of(message));
        return message;
    }

    private static TurnContext contextOf(AgentType type, Map<String, Object> config) {
        return new TurnContext(
                List.of(new TurnContext.CoverLetterPart(1, "문항", "답변", 500)),
                "봐줘", null, null, List.of(), Map.of(type.key(), config));
    }
}

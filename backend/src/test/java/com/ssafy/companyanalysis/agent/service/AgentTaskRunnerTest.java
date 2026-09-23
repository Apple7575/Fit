package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.ai.CompanyAnalysisClient;
import com.ssafy.companyanalysis.agent.domain.AgentType;
import com.ssafy.companyanalysis.agent.domain.Evidence;
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
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;

/**
 * 백엔드에 남은 담당은 기업 RAG 하나뿐이다. 나머지는 AI 총괄이 맡는다
 * ({@link SupervisorTurnRunnerTest}).
 */
class AgentTaskRunnerTest {

    private static final Long MESSAGE_ID = 31L;

    private MessageRepository messageRepository;
    private CompanyAnalysisClient companyAnalysisClient;
    private AgentTaskRunner runner;

    @BeforeEach
    void setUp() {
        messageRepository = Mockito.mock(MessageRepository.class);
        companyAnalysisClient = Mockito.mock(CompanyAnalysisClient.class);
        runner = new AgentTaskRunner(messageRepository, companyAnalysisClient);
    }

    @Test
    @DisplayName("기업 RAG 담당은 무상태 대화 API 를 직접 불러 자기 자리를 채운다")
    void companyAgentAnswersThroughItsOwnApi() {
        Message message = slotOf(AgentType.COMPANY);
        Evidence evidence = new Evidence("DART_BUSINESS_REPORT", "현대자동차", 2026, null, "근거", "https://dart.fss.or.kr/x");
        given(companyAnalysisClient.answer(eq("봐줘"), eq("00126380"), any(), anyList()))
                .willReturn(new CompanyAnalysisClient.Answer("주력은 자동차입니다.", List.of(evidence)));

        runner.run(MESSAGE_ID, contextOf(AgentType.COMPANY, Map.of("corpCodes", List.of("00126380"))));

        assertThat(message.getStatus()).isEqualTo(MessageStatus.DONE);
        assertThat(message.getContent()).isEqualTo("주력은 자동차입니다.");
        assertThat(message.getEvidences()).containsExactly(evidence);
    }

    @Test
    @DisplayName("방에 들어와 도는 첫 턴에는 대화 대신 기업 리포트를 펼친다")
    void firstTurnShowsTheReportInsteadOfChatting() {
        Message message = slotOf(AgentType.COMPANY);
        given(companyAnalysisClient.report("00126380"))
                .willReturn(new CompanyAnalysisClient.Answer("## 삼성전자 기업 분석", List.of()));

        runner.run(MESSAGE_ID, contextOf(AgentType.COMPANY, Map.of("corpCodes", List.of("00126380")), true));

        assertThat(message.getStatus()).isEqualTo(MessageStatus.DONE);
        // 마크다운이 섞여 와도 평문으로 남는다. 화면이 기호를 그리지 않는다.
        assertThat(message.getContent()).isEqualTo("삼성전자 기업 분석");
        Mockito.verify(companyAnalysisClient, Mockito.never())
                .answer(Mockito.any(), Mockito.any(), Mockito.any(), Mockito.anyList());
    }

    @Test
    @DisplayName("담당 API 가 실패하면 그 자리만 실패로 남는다")
    void companyAgentFailureStaysInItsOwnSlot() {
        Message message = slotOf(AgentType.COMPANY);
        given(companyAnalysisClient.answer(any(), any(), any(), anyList()))
                .willThrow(new IllegalStateException("AI 죽음"));

        runner.run(MESSAGE_ID, contextOf(AgentType.COMPANY, Map.of("corpCodes", List.of("00126380"))));

        assertThat(message.getStatus()).isEqualTo(MessageStatus.FAILED);
        assertThat(message.getError()).isEqualTo("지금은 이 에이전트를 쓸 수 없습니다.");
    }

    @Test
    @DisplayName("기업 코드가 여덟 자리가 아니면 AI 를 부르지 않는다")
    void companyAgentRejectsMalformedCorpCode() {
        Message message = slotOf(AgentType.COMPANY);

        runner.run(MESSAGE_ID, contextOf(AgentType.COMPANY, Map.of("corpCodes", List.of("126380"))));

        assertThat(message.getStatus()).isEqualTo(MessageStatus.FAILED);
        assertThat(message.getError()).contains("기업 코드가 올바르지 않습니다");
        Mockito.verifyNoInteractions(companyAnalysisClient);
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
        return contextOf(type, config, false);
    }

    private static TurnContext contextOf(AgentType type, Map<String, Object> config, boolean autoReview) {
        return new TurnContext(
                List.of(new TurnContext.CoverLetterPart(1, "문항", "답변", 500)),
                "봐줘", null, null, List.of(), Map.of(type.key(), config), autoReview);
    }
}

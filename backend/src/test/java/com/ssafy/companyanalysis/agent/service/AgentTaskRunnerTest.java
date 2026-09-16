package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.ai.AgentLlmClient;
import com.ssafy.companyanalysis.agent.ai.PositionAnalysisClient;
import com.ssafy.companyanalysis.agent.ai.WritingCoachingClient;
import com.ssafy.companyanalysis.agent.crawl.CompanyNewsDigest;
import com.ssafy.companyanalysis.agent.domain.AgentType;
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

import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;

class AgentTaskRunnerTest {

    private static final Long MESSAGE_ID = 31L;

    private MessageRepository messageRepository;
    private AgentLlmClient llmClient;
    private PositionAnalysisClient positionClient;
    private WritingCoachingClient writingClient;
    private AgentTaskRunner runner;

    @BeforeEach
    void setUp() {
        messageRepository = Mockito.mock(MessageRepository.class);
        llmClient = Mockito.mock(AgentLlmClient.class);
        positionClient = Mockito.mock(PositionAnalysisClient.class);
        writingClient = Mockito.mock(WritingCoachingClient.class);
        runner = new AgentTaskRunner(messageRepository, llmClient, positionClient, writingClient,
                Mockito.mock(CompanyNewsDigest.class));
    }

    @Test
    @DisplayName("포지션 담당은 자소서 답변을 근거 문서로 보내고 받은 문구를 그대로 남긴다")
    void positionAgentSendsAnsweredItemsAsDocuments() {
        Message message = slotOf(AgentType.POSITION);
        given(positionClient.analyze(anyString(), any(), any(), any()))
                .willReturn("담당 역할을 더 구체적으로 써 주세요.");

        runner.run(MESSAGE_ID, contextOf(AgentType.POSITION,
                Map.of("jobRole", "서버 개발(Java/Spring)"), null,
                part(1, "협업 경험을 써 주세요.", "API 응답 시간을 개선했습니다.", 700),
                part(2, "아직 안 쓴 문항", "  ", 500)));

        ArgumentCaptor<List<PositionAnalysisClient.Document>> documents =
                ArgumentCaptor.forClass(List.class);
        ArgumentCaptor<String> positionName = ArgumentCaptor.forClass(String.class);
        Mockito.verify(positionClient)
                .analyze(positionName.capture(), any(), documents.capture(), any());

        // 고정 목록이 없어져 공고에 쓰인 문구가 그대로 넘어간다(S15P21A504-139).
        assertThat(positionName.getValue()).isEqualTo("서버 개발(Java/Spring)");
        assertThat(documents.getValue()).hasSize(1);
        assertThat(documents.getValue().getFirst().documentId()).isEqualTo("cover-letter-item-1");
        assertThat(documents.getValue().getFirst().type()).isEqualTo("SELF_INTRO");
        assertThat(message.getStatus()).isEqualTo(MessageStatus.DONE);
        assertThat(message.getContent()).isEqualTo("담당 역할을 더 구체적으로 써 주세요.");
    }

    @Test
    @DisplayName("글쓰기 담당은 문항마다 부르고 제안 수정문을 함께 남긴다")
    void writingAgentCallsPerItem() {
        Message message = slotOf(AgentType.WRITING);
        given(writingClient.revise(anyString(), anyString(), anyString(), anyInt(), any()))
                .willReturn(new WritingCoachingClient.Revision(
                        "REVISED", "첫 문장을 다듬었습니다.", "팀에서 역할을 나눠 해결했습니다."));

        runner.run(MESSAGE_ID, contextOf(AgentType.WRITING, Map.of(), "두괄식으로 고쳐줘",
                part(1, "협업 경험", "팀 프로젝트에서 역할을 나누고 함께 해결했습니다.", 700)));

        Mockito.verify(writingClient).revise("두괄식으로 고쳐줘", "협업 경험",
                "팀 프로젝트에서 역할을 나누고 함께 해결했습니다.", 700, List.of());
        assertThat(message.getContent())
                .contains("문항 1. 첫 문장을 다듬었습니다.")
                .contains("[제안] 팀에서 역할을 나눠 해결했습니다.");
    }

    @Test
    @DisplayName("문항이 세 개를 넘으면 앞에서 세 개만 보고 나머지는 안내한다")
    void writingAgentStopsAtThreeItems() {
        Message message = slotOf(AgentType.WRITING);
        given(writingClient.revise(anyString(), anyString(), anyString(), anyInt(), any()))
                .willReturn(new WritingCoachingClient.Revision("ANSWERED", "이대로도 괜찮습니다.", null));

        runner.run(MESSAGE_ID, contextOf(AgentType.WRITING, Map.of(), null,
                part(1, "문항 1", "답변 1", 500),
                part(2, "문항 2", "답변 2", 500),
                part(3, "문항 3", "답변 3", 500),
                part(4, "문항 4", "답변 4", 500)));

        Mockito.verify(writingClient, Mockito.times(3))
                .revise(anyString(), anyString(), anyString(), anyInt(), any());
        assertThat(message.getContent()).contains("나머지는 문항을 골라 다시 요청해 주세요.");
    }

    @Test
    @DisplayName("AI 서버가 막혀 있으면 그 에이전트만 실패로 남는다")
    void agentFailsAloneWhenAiIsDown() {
        Message message = slotOf(AgentType.POSITION);
        willThrow(new BusinessException(ErrorCode.AI_UNAVAILABLE,
                "포지션 담당 AI 서버가 아직 모델에 연결되지 않았습니다."))
                .given(positionClient).analyze(anyString(), any(), any(), any());

        runner.run(MESSAGE_ID, contextOf(AgentType.POSITION, Map.of("jobRole", "backend"), null,
                part(1, "협업 경험", "함께 해결했습니다.", 700)));

        assertThat(message.getStatus()).isEqualTo(MessageStatus.FAILED);
        assertThat(message.getError()).contains("AI 서버가 아직 모델에 연결되지 않았습니다");
    }

    @Test
    @DisplayName("답변을 하나도 안 썼으면 부르지 않고 실패로 남는다")
    void writingAgentFailsWithoutAnswers() {
        Message message = slotOf(AgentType.WRITING);

        runner.run(MESSAGE_ID, contextOf(AgentType.WRITING, Map.of(), null,
                part(1, "문항 1", "", 500)));

        Mockito.verifyNoInteractions(writingClient);
        assertThat(message.getStatus()).isEqualTo(MessageStatus.FAILED);
        assertThat(message.getError()).isEqualTo("검토할 자소서 답변이 없습니다.");
    }

    private Message slotOf(AgentType type) {
        Message message = Message.pendingAgent(9L, 8L, type.key());
        given(messageRepository.findById(MESSAGE_ID)).willReturn(Optional.of(message));
        return message;
    }

    private static TurnContext contextOf(AgentType type,
                                         Map<String, Object> config,
                                         String userMessage,
                                         TurnContext.CoverLetterPart... parts) {
        return new TurnContext("자소서 본문", List.of(parts), userMessage, null,
                Map.of(type.key(), config));
    }

    private static TurnContext.CoverLetterPart part(int seq, String question, String answer,
                                                    int charLimit) {
        return new TurnContext.CoverLetterPart(seq, question, answer, charLimit);
    }
}

package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.domain.JobContext;
import com.ssafy.companyanalysis.agent.domain.Message;
import com.ssafy.companyanalysis.agent.domain.MessageStatus;
import com.ssafy.companyanalysis.agent.domain.Room;
import com.ssafy.companyanalysis.agent.domain.RoomAgent;
import com.ssafy.companyanalysis.agent.dto.MessageSendRequest;
import com.ssafy.companyanalysis.agent.dto.TurnStartedResponse;
import com.ssafy.companyanalysis.agent.dto.TurnStatusResponse;
import com.ssafy.companyanalysis.agent.repository.JobContextRepository;
import com.ssafy.companyanalysis.agent.repository.MessageRepository;
import com.ssafy.companyanalysis.agent.repository.RoomRepository;
import com.ssafy.companyanalysis.coverletter.domain.CoverLetterItem;
import com.ssafy.companyanalysis.coverletter.repository.CoverLetterItemRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.mockito.Mockito;

import java.lang.reflect.Field;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicLong;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

class TurnServiceTest {

    private static final Long USER = 7L;
    private static final Long ROOM = 31L;

    private RoomRepository roomRepository;
    private MessageRepository messageRepository;
    private JobContextRepository jobContextRepository;
    private CoverLetterItemRepository itemRepository;
    private TurnExecutor turnExecutor;
    private TurnService service;

    /** 저장 시점에 DB 가 채우는 id 를 테스트에서 흉내 낸다. 턴 식별자가 곧 사용자 발화 id 라 필요하다. */
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

    @BeforeEach
    void setUp() {
        roomRepository = Mockito.mock(RoomRepository.class);
        messageRepository = Mockito.mock(MessageRepository.class);
        itemRepository = Mockito.mock(CoverLetterItemRepository.class);
        turnExecutor = Mockito.mock(TurnExecutor.class);
        jobContextRepository = Mockito.mock(JobContextRepository.class);
        service = new TurnService(roomRepository, messageRepository, jobContextRepository,
                itemRepository, turnExecutor,
                new AnalysisRateLimiter(100, java.time.Duration.ofHours(1)),
                noTransaction());

        AtomicLong seq = new AtomicLong(100);
        given(messageRepository.save(any(Message.class)))
                .willAnswer(call -> withId(call.getArgument(0), seq.incrementAndGet()));
        given(messageRepository.saveAll(any()))
                .willAnswer(call -> {
                    List<Message> given = call.getArgument(0);
                    given.forEach(m -> withId(m, seq.incrementAndGet()));
                    return given;
                });
        given(itemRepository.findByCoverLetterIdOrderBySeqAsc(anyLong()))
                .willReturn(List.of(withItemId(CoverLetterItem.create(12L, 1, "질문", "답변", 1000), 500L)));
    }

    /**
     * 트랜잭션 경계만 있고 실제로 아무것도 하지 않는 관리자. 여기서는 저장소가 다 가짜라
     * 커밋할 것이 없고, 확인하려는 것은 뿌리와 자리를 한 번에 만드느냐이지 커밋 자체가 아니다.
     */
    private static org.springframework.transaction.PlatformTransactionManager noTransaction() {
        return new org.springframework.transaction.PlatformTransactionManager() {
            @Override
            public org.springframework.transaction.TransactionStatus getTransaction(
                    org.springframework.transaction.TransactionDefinition definition) {
                return new org.springframework.transaction.support.SimpleTransactionStatus();
            }

            @Override
            public void commit(org.springframework.transaction.TransactionStatus status) {
            }

            @Override
            public void rollback(org.springframework.transaction.TransactionStatus status) {
            }
        };
    }

    private static CoverLetterItem withItemId(CoverLetterItem item, long id) {
        try {
            Field field = CoverLetterItem.class.getDeclaredField("id");
            field.setAccessible(true);
            field.set(item, id);
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException(e);
        }
        return item;
    }

    private void roomWith(String... agentKeys) {
        Room room = Room.create(USER, 12L, "검토 방",
                java.util.Arrays.stream(agentKeys).map(k -> new RoomAgent(k, Map.of())).toList());
        given(roomRepository.findByIdAndUserId(ROOM, USER)).willReturn(Optional.of(room));
    }

    private void roomWithJobContext(String contextId, String... agentKeys) {
        Room room = Room.create(USER, 12L, contextId, "검토 방",
                java.util.Arrays.stream(agentKeys).map(k -> new RoomAgent(k, Map.of())).toList());
        given(roomRepository.findByIdAndUserId(ROOM, USER)).willReturn(Optional.of(room));
    }

    private static JobContext jobContext(String contextId, String positionName) {
        JobContext context = Mockito.mock(JobContext.class);
        given(context.getContextId()).willReturn(contextId);
        given(context.getPositionName()).willReturn(positionName);
        return context;
    }

    @Test
    @DisplayName("방에 붙은 공고는 턴을 시작할 때 한 번 확인해 식별자와 직무명만 싣는다")
    void jobPostingIsCheckedOnceAndOnlyItsIdentifiersTravel() {
        roomWithJobContext("ctx-1", "jd", "writing");
        // 스터빙 안에서 또 스터빙하면 Mockito 가 끝나지 않은 스터빙으로 본다. 먼저 만들어 둔다.
        JobContext context = jobContext("ctx-1", "백엔드");
        given(jobContextRepository.findById("ctx-1")).willReturn(Optional.of(context));

        service.start(USER, ROOM, new MessageSendRequest("봐줘", null));

        ArgumentCaptor<TurnContext> captor = ArgumentCaptor.forClass(TurnContext.class);
        then(turnExecutor).should().runTurn(anyLong(), captor.capture());
        assertThat(captor.getValue().hasJobContext()).isTrue();
        assertThat(captor.getValue().jobContextId()).isEqualTo("ctx-1");
        assertThat(captor.getValue().jobPositionName()).isEqualTo("백엔드");
        then(jobContextRepository).should().findById("ctx-1");
    }

    @Test
    @DisplayName("공고 없이 연 방은 공고를 조회하지 않는다")
    void roomWithoutJobPostingSkipsTheLookup() {
        roomWith("writing");

        service.start(USER, ROOM, new MessageSendRequest("봐줘", null));

        ArgumentCaptor<TurnContext> captor = ArgumentCaptor.forClass(TurnContext.class);
        then(turnExecutor).should().runTurn(anyLong(), captor.capture());
        assertThat(captor.getValue().hasJobContext()).isFalse();
        then(jobContextRepository).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("분석이 사라졌으면 식별자를 넘기지 않는다 — 없는 id 를 보내면 AI 가 404 를 준다")
    void missingAnalysisDropsTheJobContextId() {
        roomWithJobContext("ctx-gone", "writing");
        given(jobContextRepository.findById("ctx-gone")).willReturn(Optional.empty());

        service.start(USER, ROOM, new MessageSendRequest("봐줘", null));

        ArgumentCaptor<TurnContext> captor = ArgumentCaptor.forClass(TurnContext.class);
        then(turnExecutor).should().runTurn(anyLong(), captor.capture());
        assertThat(captor.getValue().hasJobContext()).isFalse();
    }

    @Test
    @DisplayName("지난 대화는 오래된 것부터 실어 보낸다 — AI 총괄이 대화를 들고 있지 않다")
    void pastMessagesTravelWithEveryTurn() {
        roomWith("writing");
        Message earlier = withId(Message.fromUser(ROOM, "근거 중심으로 정리해줘"), 40L);
        Message answer = withId(Message.pendingAgent(ROOM, 40L, "writing"), 41L);
        answer.succeed("첫 문장을 앞으로 올렸습니다.", List.of(), List.of());
        Message stillRunning = withId(Message.pendingAgent(ROOM, 40L, "position"), 42L);
        given(messageRepository.findPage(any(), any(), any()))
                .willReturn(List.of(stillRunning, answer, earlier));

        service.start(USER, ROOM, new MessageSendRequest("봐줘", null));

        ArgumentCaptor<TurnContext> captor = ArgumentCaptor.forClass(TurnContext.class);
        then(turnExecutor).should().runTurn(anyLong(), captor.capture());
        assertThat(captor.getValue().conversation())
                .extracting(com.ssafy.companyanalysis.agent.ai.SupervisorClient.Turn::role)
                .containsExactly("USER", "ASSISTANT");
    }

    @Test
    @DisplayName("발화하면 사용자 메시지의 id 가 곧 턴 식별자다")
    void turnIdIsTheUserMessageId() {
        roomWith("writing", "position");

        TurnStartedResponse response = service.start(USER, ROOM, new MessageSendRequest("봐줘", null));

        assertThat(response.turnId()).isEqualTo(response.messageId());
        assertThat(response.status()).isEqualTo("PENDING");
    }

    @Test
    @DisplayName("방에서 고르지 않은 담당도 재료가 있으면 자리를 만든다 — 고르는 일은 AI 총괄이 한다")
    void everyFillableAgentGetsASlotEvenIfTheRoomDidNotPickIt() {
        roomWithJobContext("ctx-1", "writing");
        JobContext context = jobContext("ctx-1", "백엔드");
        given(jobContextRepository.findById("ctx-1")).willReturn(Optional.of(context));

        TurnStartedResponse response = service.start(USER, ROOM, new MessageSendRequest("봐줘", null));

        assertThat(response.agents()).extracting(TurnStartedResponse.AgentSlot::agentKey)
                .containsExactly("jd", "position", "writing", "supervisor");
    }

    @Test
    @DisplayName("기업 RAG 담당은 방에서 고른 경우에만 자리를 만든다 — 아직 백엔드가 맡고 있다")
    void companyAgentStillFollowsTheRoomSelection() {
        roomWith("company");

        TurnStartedResponse response = service.start(USER, ROOM, new MessageSendRequest("봐줘", null));

        assertThat(response.agents()).extracting(TurnStartedResponse.AgentSlot::agentKey)
                .containsExactly("writing", "company", "supervisor");
    }

    @Test
    @DisplayName("돌릴 담당이 하나뿐인 턴은 총괄 자리를 만들지 않는다")
    void soloRoomHasNoSupervisorSlot() {
        roomWith("writing");

        TurnStartedResponse response = service.start(USER, ROOM, new MessageSendRequest("봐줘", null));

        assertThat(response.agents()).extracting(TurnStartedResponse.AgentSlot::agentKey)
                .containsExactly("writing");
    }

    @Test
    @DisplayName("공고도 없고 답변도 없으면 400 — 보낼 재료가 없다")
    void turnWithNothingToSendIsRejected() {
        roomWith("writing");
        given(itemRepository.findByCoverLetterIdOrderBySeqAsc(anyLong()))
                .willReturn(List.of(withItemId(CoverLetterItem.create(12L, 1, "질문", "  ", 1000), 500L)));

        assertThatThrownBy(() -> service.start(USER, ROOM, new MessageSendRequest("봐줘", null)))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.INVALID_PARAMETER);
    }

    @Test
    @DisplayName("발화는 결과를 기다리지 않고 실행만 띄운다")
    void executionIsHandedOffNotAwaited() {
        roomWith("writing");

        service.start(USER, ROOM, new MessageSendRequest("봐줘", null));

        then(turnExecutor).should().runTurn(anyLong(), any(TurnContext.class));
    }

    @Test
    @DisplayName("아직 끝나지 않은 턴이 있으면 409")
    void concurrentTurnIsRejected() {
        roomWith("writing");
        given(messageRepository.existsByRoomIdAndStatusIn(any(), any())).willReturn(true);

        assertThatThrownBy(() -> service.start(USER, ROOM, new MessageSendRequest("봐줘", null)))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.TURN_IN_PROGRESS);
    }

    @Test
    @DisplayName("남의 방에는 말을 걸 수 없다")
    void cannotSpeakInSomeoneElsesRoom() {
        given(roomRepository.findByIdAndUserId(ROOM, 99L)).willReturn(Optional.empty());

        assertThatThrownBy(() -> service.start(99L, ROOM, new MessageSendRequest("봐줘", null)))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.ROOM_NOT_FOUND);
    }

    @Test
    @DisplayName("이 자소서의 문항이 아니면 400")
    void unknownCoverLetterItemIsRejected() {
        roomWith("writing");

        assertThatThrownBy(() -> service.start(USER, ROOM, new MessageSendRequest("봐줘", 999L)))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.INVALID_PARAMETER);
    }

    @Test
    @DisplayName("한 에이전트가 실패해도 턴은 실패가 아니라 계속 간다")
    void oneFailedAgentDoesNotFailTheTurn() {
        roomWith("writing", "position");
        Message turn = withId(Message.fromUser(ROOM, "봐줘"), 100L);
        Message ok = withId(Message.pendingAgent(ROOM, 100L, "writing"), 101L);
        ok.succeed("고쳤습니다", List.of(), List.of());
        Message failed = withId(Message.pendingAgent(ROOM, 100L, "position"), 102L);
        failed.fail("자료 없음");
        Message supervisor = withId(Message.pendingAgent(ROOM, 100L, "supervisor"), 103L);

        given(messageRepository.findByIdAndRoomId(100L, ROOM)).willReturn(Optional.of(turn));
        given(messageRepository.findByParentMessageIdOrderByIdAsc(100L))
                .willReturn(List.of(ok, failed, supervisor));

        TurnStatusResponse status = service.status(USER, ROOM, 100L);

        // 에이전트는 끝났고 총괄이 남았으므로 아직 진행 중이다
        assertThat(status.status()).isEqualTo(MessageStatus.RUNNING.name());
        assertThat(status.agents()).extracting(TurnStatusResponse.AgentProgress::status)
                .containsExactly("DONE", "FAILED");
        assertThat(status.agents().get(1).error()).isEqualTo("자료 없음");
        assertThat(status.supervisor().agentKey()).isEqualTo("supervisor");
    }

    @Test
    @DisplayName("총괄까지 끝나면 턴이 끝난 것이다")
    void turnIsDoneWhenSupervisorFinishes() {
        roomWith("writing", "position");
        Message turn = withId(Message.fromUser(ROOM, "봐줘"), 100L);
        Message ok = withId(Message.pendingAgent(ROOM, 100L, "writing"), 101L);
        ok.succeed("고쳤습니다", List.of(), List.of());
        Message supervisor = withId(Message.pendingAgent(ROOM, 100L, "supervisor"), 103L);
        supervisor.succeed("종합했습니다", List.of(), List.of(101L));

        given(messageRepository.findByIdAndRoomId(100L, ROOM)).willReturn(Optional.of(turn));
        given(messageRepository.findByParentMessageIdOrderByIdAsc(100L))
                .willReturn(List.of(ok, supervisor));

        assertThat(service.status(USER, ROOM, 100L).status()).isEqualTo(MessageStatus.DONE.name());
    }

    @Test
    @DisplayName("없는 턴은 404")
    void unknownTurnIsNotFound() {
        roomWith("writing");
        given(messageRepository.findByIdAndRoomId(999L, ROOM)).willReturn(Optional.empty());

        assertThatThrownBy(() -> service.status(USER, ROOM, 999L))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.TURN_NOT_FOUND);
    }

    @Test
    @DisplayName("자동 검토는 사용자가 하지 않은 말을 지어내지 않는다 — 턴의 뿌리가 비어 있다")
    void autoReviewLeavesTheRootEmpty() {
        roomWith("writing", "position");

        service.autoReview(USER, ROOM);

        ArgumentCaptor<Message> captor = ArgumentCaptor.forClass(Message.class);
        then(messageRepository).should().save(captor.capture());
        assertThat(captor.getValue().getContent()).isNull();
        assertThat(captor.getValue().getStatus()).isEqualTo(MessageStatus.DONE);
    }

    @Test
    @DisplayName("자동 검토는 총괄에게 기본 지시문을 보낸다 — 지시문 없이는 무엇을 할지 정하지 못한다")
    void autoReviewSendsADefaultInstruction() {
        roomWith("writing");

        service.autoReview(USER, ROOM);

        ArgumentCaptor<TurnContext> captor = ArgumentCaptor.forClass(TurnContext.class);
        then(turnExecutor).should().runTurnNow(anyLong(), captor.capture());
        assertThat(captor.getValue().userMessage()).isNotBlank();
        assertThat(captor.getValue().answeredParts()).isNotEmpty();
    }

    @Test
    @DisplayName("자동 검토는 부른 스레드에서 끝까지 돈다 — 방을 하나씩 차례로 돌리기 위한 것이다")
    void autoReviewRunsOnTheCallingThread() {
        roomWith("writing");

        service.autoReview(USER, ROOM);

        then(turnExecutor).should().runTurnNow(anyLong(), any());
        then(turnExecutor).should(Mockito.never()).runTurn(anyLong(), any());
    }

    @Test
    @DisplayName("이미 말이 오간 방은 자동 검토가 물러난다")
    void autoReviewSkipsRoomThatAlreadyTalked() {
        roomWith("writing");
        given(messageRepository.existsByRoomId(ROOM)).willReturn(true);

        service.autoReview(USER, ROOM);

        then(turnExecutor).shouldHaveNoInteractions();
        then(messageRepository).should(Mockito.never()).save(any(Message.class));
    }

    @Test
    @DisplayName("아직 문항이 없는 자소서는 검토할 것이 없어 건너뛴다 — 방이 깔리는 것까지 막지 않는다")
    void autoReviewSkipsEmptyCoverLetter() {
        roomWith("writing");
        given(itemRepository.findByCoverLetterIdOrderBySeqAsc(anyLong())).willReturn(List.of());

        service.autoReview(USER, ROOM);

        then(turnExecutor).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("자동 검토도 재료가 있는 담당마다 자리를 만들고, 둘 이상이면 총괄이 붙는다")
    void autoReviewOpensSlotsForEveryAgent() {
        // 직무를 채워야 포지션 담당에게 넘길 재료가 생긴다. 재료가 없는 담당은 자리도 만들지 않는다.
        Room room = Room.create(USER, 12L, "검토 방", List.of(
                new RoomAgent("writing", Map.of()),
                new RoomAgent("position", Map.of("jobRole", "백엔드 개발"))));
        given(roomRepository.findByIdAndUserId(ROOM, USER)).willReturn(Optional.of(room));

        service.autoReview(USER, ROOM);

        ArgumentCaptor<List<Message>> captor = ArgumentCaptor.forClass(List.class);
        then(messageRepository).should().saveAll(captor.capture());
        assertThat(captor.getValue()).extracting(Message::getAgentKey)
                .contains("writing", "position", "supervisor");
    }
}

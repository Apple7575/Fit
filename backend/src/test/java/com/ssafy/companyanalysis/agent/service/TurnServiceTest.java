package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.domain.Message;
import com.ssafy.companyanalysis.agent.domain.MessageStatus;
import com.ssafy.companyanalysis.agent.domain.Room;
import com.ssafy.companyanalysis.agent.domain.RoomAgent;
import com.ssafy.companyanalysis.agent.dto.MessageSendRequest;
import com.ssafy.companyanalysis.agent.dto.TurnStartedResponse;
import com.ssafy.companyanalysis.agent.dto.TurnStatusResponse;
import com.ssafy.companyanalysis.agent.repository.MessageRepository;
import com.ssafy.companyanalysis.agent.repository.RoomRepository;
import com.ssafy.companyanalysis.coverletter.domain.CoverLetterItem;
import com.ssafy.companyanalysis.coverletter.repository.CoverLetterItemRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
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
        service = new TurnService(roomRepository, messageRepository, itemRepository, turnExecutor,
                new AnalysisRateLimiter(100, java.time.Duration.ofHours(1)));

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

    @Test
    @DisplayName("발화하면 사용자 메시지의 id 가 곧 턴 식별자다")
    void turnIdIsTheUserMessageId() {
        roomWith("writing", "position");

        TurnStartedResponse response = service.start(USER, ROOM, new MessageSendRequest("봐줘", null));

        assertThat(response.turnId()).isEqualTo(response.messageId());
        assertThat(response.status()).isEqualTo("PENDING");
    }

    @Test
    @DisplayName("에이전트가 2명 이상이면 총괄 자리도 함께 만든다")
    void supervisorSlotIsCreatedForJointRoom() {
        roomWith("writing", "position");

        TurnStartedResponse response = service.start(USER, ROOM, new MessageSendRequest("봐줘", null));

        assertThat(response.agents()).extracting(TurnStartedResponse.AgentSlot::agentKey)
                .containsExactly("writing", "position", "supervisor");
    }

    @Test
    @DisplayName("전담 방은 총괄 자리를 만들지 않는다")
    void soloRoomHasNoSupervisorSlot() {
        roomWith("writing");

        TurnStartedResponse response = service.start(USER, ROOM, new MessageSendRequest("봐줘", null));

        assertThat(response.agents()).extracting(TurnStartedResponse.AgentSlot::agentKey)
                .containsExactly("writing");
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
}

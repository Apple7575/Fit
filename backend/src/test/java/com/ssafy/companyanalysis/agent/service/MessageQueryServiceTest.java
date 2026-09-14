package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.domain.Message;
import com.ssafy.companyanalysis.agent.domain.Room;
import com.ssafy.companyanalysis.agent.domain.RoomAgent;
import com.ssafy.companyanalysis.agent.dto.MessageListResponse;
import com.ssafy.companyanalysis.agent.repository.MessageRepository;
import com.ssafy.companyanalysis.agent.repository.RoomRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.mockito.Mockito;
import org.springframework.data.domain.Pageable;

import java.lang.reflect.Field;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.stream.IntStream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.BDDMockito.given;

class MessageQueryServiceTest {

    private static final Long USER = 7L;
    private static final Long ROOM = 31L;

    private RoomRepository roomRepository;
    private MessageRepository messageRepository;
    private MessageQueryService service;

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
        service = new MessageQueryService(roomRepository, messageRepository);

        Room room = Room.create(USER, 12L, "검토 방", List.of(new RoomAgent("writing", Map.of())));
        given(roomRepository.findByIdAndUserId(ROOM, USER)).willReturn(Optional.of(room));
    }

    private static List<Message> agentMessages(int count, long startId) {
        return IntStream.range(0, count)
                .mapToObj(i -> withId(Message.pendingAgent(ROOM, 100L, "writing"), startId - i))
                .toList();
    }

    @Test
    @DisplayName("다음 페이지가 있으면 커서를 준다")
    void nextCursorIsGivenWhenMoreRemain() {
        // 서비스는 size+1 만큼 읽어 더 있는지 본다
        given(messageRepository.findPage(eq(ROOM), isNull(), any(Pageable.class)))
                .willReturn(agentMessages(4, 203L));

        MessageListResponse response = service.list(USER, ROOM, null, 3);

        assertThat(response.messages()).hasSize(3);
        assertThat(response.nextCursor()).isNotNull();
    }

    @Test
    @DisplayName("마지막 페이지면 커서가 없다")
    void nextCursorIsNullOnLastPage() {
        given(messageRepository.findPage(eq(ROOM), isNull(), any(Pageable.class)))
                .willReturn(agentMessages(2, 201L));

        assertThat(service.list(USER, ROOM, null, 3).nextCursor()).isNull();
    }

    @Test
    @DisplayName("받은 커서로 이어 읽으면 그보다 오래된 것만 조회한다")
    void cursorIsPassedBackToRepository() {
        given(messageRepository.findPage(eq(ROOM), isNull(), any(Pageable.class)))
                .willReturn(agentMessages(4, 203L));
        String cursor = service.list(USER, ROOM, null, 3).nextCursor();

        given(messageRepository.findPage(eq(ROOM), any(), any(Pageable.class)))
                .willReturn(List.of());
        service.list(USER, ROOM, cursor, 3);

        ArgumentCaptor<Long> captured = ArgumentCaptor.forClass(Long.class);
        Mockito.verify(messageRepository, Mockito.atLeastOnce())
                .findPage(eq(ROOM), captured.capture(), any(Pageable.class));
        assertThat(captured.getAllValues()).contains(201L);
    }

    @Test
    @DisplayName("사용자 발화는 자기 자신이 턴이고, 에이전트 답변은 딸린 발화를 가리킨다")
    void turnIdPointsAtTheUserMessage() {
        Message user = withId(Message.fromUser(ROOM, "봐줘"), 100L);
        Message agent = withId(Message.pendingAgent(ROOM, 100L, "writing"), 101L);
        given(messageRepository.findPage(eq(ROOM), isNull(), any(Pageable.class)))
                .willReturn(List.of(agent, user));

        List<MessageListResponse.Message> messages = service.list(USER, ROOM, null, 10).messages();

        assertThat(messages).extracting(MessageListResponse.Message::turnId)
                .containsExactly(100L, 100L);
        assertThat(messages).extracting(MessageListResponse.Message::role)
                .containsExactly("agent", "user");
        assertThat(messages.get(0).agentName()).isEqualTo("글쓰기 담당");
    }

    @Test
    @DisplayName("실패한 에이전트도 사유와 함께 그 자리에 남는다")
    void failedAgentStaysInTheTranscript() {
        Message failed = withId(Message.pendingAgent(ROOM, 100L, "writing"), 101L);
        failed.fail("자료가 없습니다");
        given(messageRepository.findPage(eq(ROOM), isNull(), any(Pageable.class)))
                .willReturn(List.of(failed));

        MessageListResponse.Message view = service.list(USER, ROOM, null, 10).messages().get(0);

        assertThat(view.status()).isEqualTo("FAILED");
        assertThat(view.error()).isEqualTo("자료가 없습니다");
    }

    @Test
    @DisplayName("남의 방 대화는 볼 수 없다")
    void otherUsersRoomIsNotFound() {
        given(roomRepository.findByIdAndUserId(ROOM, 99L)).willReturn(Optional.empty());

        assertThatThrownBy(() -> service.list(99L, ROOM, null, 10))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.ROOM_NOT_FOUND);
    }

    @Test
    @DisplayName("size 가 범위를 벗어나면 400")
    void sizeOutOfRangeIsRejected() {
        assertThatThrownBy(() -> service.list(USER, ROOM, null, 0))
                .isInstanceOf(BusinessException.class);
        assertThatThrownBy(() -> service.list(USER, ROOM, null, 101))
                .isInstanceOf(BusinessException.class);
    }

    @Test
    @DisplayName("망가진 커서는 400 이지 500 이 아니다")
    void brokenCursorIsBadRequest() {
        assertThatThrownBy(() -> service.list(USER, ROOM, "!!망가진커서!!", 10))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.INVALID_PARAMETER);
    }
}

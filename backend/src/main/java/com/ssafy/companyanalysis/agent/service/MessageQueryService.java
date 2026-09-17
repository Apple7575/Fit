package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.domain.AgentType;
import com.ssafy.companyanalysis.agent.domain.Message;
import com.ssafy.companyanalysis.agent.domain.MessageRole;
import com.ssafy.companyanalysis.agent.dto.MessageListResponse;
import com.ssafy.companyanalysis.agent.repository.MessageRepository;
import com.ssafy.companyanalysis.agent.repository.RoomRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.List;

/** 방의 대화를 읽는다. 쓰기는 {@link TurnService} 가 한다. */
@Service
@Transactional(readOnly = true)
public class MessageQueryService {

    private static final int DEFAULT_SIZE = 30;
    private static final int MAX_SIZE = 100;

    private final RoomRepository roomRepository;
    private final MessageRepository messageRepository;

    public MessageQueryService(RoomRepository roomRepository, MessageRepository messageRepository) {
        this.roomRepository = roomRepository;
        this.messageRepository = messageRepository;
    }

    public MessageListResponse list(Long userId, Long roomId, String cursor, Integer size) {
        if (roomRepository.findByIdAndUserId(roomId, userId).isEmpty()) {
            throw new BusinessException(ErrorCode.ROOM_NOT_FOUND, "검토 방을 찾을 수 없습니다: " + roomId);
        }
        int pageSize = resolveSize(size);

        // 한 건 더 읽어 다음 페이지가 있는지 본다. 개수를 따로 세면 쿼리가 한 번 더 나간다.
        List<Message> found = messageRepository.findPage(roomId, decodeCursor(cursor),
                PageRequest.of(0, pageSize + 1));

        boolean hasMore = found.size() > pageSize;
        List<Message> page = hasMore ? found.subList(0, pageSize) : found;

        return new MessageListResponse(
                page.stream().map(MessageQueryService::toView).toList(),
                hasMore ? encodeCursor(page.get(page.size() - 1).getId()) : null);
    }

    private static MessageListResponse.Message toView(Message message) {
        boolean fromUser = message.getRole() == MessageRole.USER;
        return new MessageListResponse.Message(
                message.getId(),
                // 사용자 발화는 자기 자신이 턴이다.
                fromUser ? message.getId() : message.getParentMessageId(),
                message.getRole().name().toLowerCase(),
                message.getAgentKey(),
                AgentType.from(message.getAgentKey()).map(AgentType::displayName).orElse(null),
                message.getContent(),
                message.getEvidences(),
                message.getBasedOn(),
                message.getStatus().name(),
                message.getError(),
                message.getCreatedAt());
    }

    private static int resolveSize(Integer size) {
        if (size == null) {
            return DEFAULT_SIZE;
        }
        if (size < 1 || size > MAX_SIZE) {
            throw new BusinessException(ErrorCode.INVALID_PARAMETER,
                    "size 는 1 이상 " + MAX_SIZE + " 이하여야 합니다.");
        }
        return size;
    }

    /** 커서는 프론트가 뜯어보지 않도록 감싼 값이다. 내용은 마지막으로 읽은 메시지 id 다. */
    private static String encodeCursor(Long lastId) {
        return Base64.getUrlEncoder().withoutPadding()
                .encodeToString(String.valueOf(lastId).getBytes(StandardCharsets.UTF_8));
    }

    private static Long decodeCursor(String cursor) {
        if (cursor == null || cursor.isBlank()) {
            return null;
        }
        try {
            return Long.parseLong(new String(Base64.getUrlDecoder().decode(cursor), StandardCharsets.UTF_8));
        } catch (IllegalArgumentException e) {
            throw new BusinessException(ErrorCode.INVALID_PARAMETER, "cursor 가 올바르지 않습니다.");
        }
    }
}

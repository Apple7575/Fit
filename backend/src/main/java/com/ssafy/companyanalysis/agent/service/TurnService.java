package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.domain.AgentType;
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
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 발화를 받아 턴을 시작하고 진행 상황을 알려준다.
 *
 * <p>발화는 결과를 기다리지 않고 turnId 만 돌려준다. 에이전트 다섯이 각자 LLM 을 부르면
 * 1분을 넘겨 연결이 끊긴다.
 */
@Service
public class TurnService {

    private static final List<MessageStatus> UNFINISHED =
            List.of(MessageStatus.PENDING, MessageStatus.RUNNING);

    private final RoomRepository roomRepository;
    private final MessageRepository messageRepository;
    private final JobContextRepository jobContextRepository;
    private final CoverLetterItemRepository coverLetterItemRepository;
    private final TurnExecutor turnExecutor;
    private final AnalysisRateLimiter rateLimiter;

    public TurnService(RoomRepository roomRepository,
                       MessageRepository messageRepository,
                       JobContextRepository jobContextRepository,
                       CoverLetterItemRepository coverLetterItemRepository,
                       TurnExecutor turnExecutor,
                       AnalysisRateLimiter rateLimiter) {
        this.roomRepository = roomRepository;
        this.messageRepository = messageRepository;
        this.jobContextRepository = jobContextRepository;
        this.coverLetterItemRepository = coverLetterItemRepository;
        this.turnExecutor = turnExecutor;
        this.rateLimiter = rateLimiter;
    }

    /**
     * 발화를 저장하고 에이전트 자리를 만든 뒤 실행을 띄운다.
     *
     * <p>트랜잭션을 걸지 않는다. 실행 스레드가 곧바로 메시지를 읽어야 하는데, 열린 트랜잭션
     * 안에서 띄우면 아직 커밋되지 않은 행을 못 본다.
     */
    public TurnStartedResponse start(Long userId, Long roomId, MessageSendRequest request) {
        Room room = ownedRoom(userId, roomId);
        if (messageRepository.existsByRoomIdAndStatusIn(roomId, UNFINISHED)) {
            throw new BusinessException(ErrorCode.TURN_IN_PROGRESS,
                    "이전 요청이 아직 끝나지 않았습니다.");
        }
        rateLimiter.check(userId);

        List<CoverLetterItem> items = targetItems(room, request.coverLetterItemId());
        Message userMessage = messageRepository.save(
                Message.fromUser(roomId, request.content().trim()));

        List<String> agentKeys = participants(room);
        List<Message> slots = agentKeys.stream()
                .map(key -> Message.pendingAgent(roomId, userMessage.getId(), key))
                .toList();
        messageRepository.saveAll(slots);

        turnExecutor.runTurn(userMessage.getId(),
                new TurnContext(joinedText(items), partsOf(items), request.content().trim(),
                        jobPostingText(room), configsOf(room)));

        return new TurnStartedResponse(
                userMessage.getId(),
                userMessage.getId(),
                MessageStatus.PENDING.name(),
                slots.stream()
                        .map(slot -> new TurnStartedResponse.AgentSlot(
                                slot.getAgentKey(), slot.getStatus().name()))
                        .toList());
    }

    /**
     * 방에 붙은 공고 본문. 턴을 시작할 때 한 번만 읽어 참여 에이전트 전부가 같은 것을 본다.
     *
     * <p>분석이 사라졌으면 공고 없는 방으로 본다. 공고를 보는 에이전트만 자기 자리에서 실패한다.
     */
    private String jobPostingText(Room room) {
        if (room.getJobContextId() == null) {
            return null;
        }
        return jobContextRepository.findById(room.getJobContextId())
                .map(context -> "[" + context.getCompanyName() + " · " + context.getPositionName()
                        + "]\n" + context.getJdText())
                .orElse(null);
    }

    /** 턴 상태는 저장하지 않고 자식들의 상태를 모아 계산한다. */
    @Transactional(readOnly = true)
    public TurnStatusResponse status(Long userId, Long roomId, Long turnId) {
        ownedRoom(userId, roomId);
        Message turn = messageRepository.findByIdAndRoomId(turnId, roomId)
                .orElseThrow(() -> new BusinessException(ErrorCode.TURN_NOT_FOUND,
                        "요청 기록을 찾을 수 없습니다: " + turnId));

        List<Message> children = messageRepository.findByParentMessageIdOrderByIdAsc(turn.getId());
        List<Message> agents = children.stream()
                .filter(m -> !AgentType.SUPERVISOR.key().equals(m.getAgentKey()))
                .toList();
        Message supervisor = children.stream()
                .filter(m -> AgentType.SUPERVISOR.key().equals(m.getAgentKey()))
                .findFirst().orElse(null);

        return new TurnStatusResponse(
                turn.getId(),
                aggregate(agents, supervisor).name(),
                agents.stream().map(TurnService::toView).toList(),
                supervisor == null ? null : toView(supervisor));
    }

    /**
     * 한 에이전트가 실패해도 턴은 실패가 아니다. 전원이 끝났는데 총괄이 아직이면 SUPERVISING,
     * 총괄까지 끝나면 DONE 이다. 총괄이 없는 전담 방은 에이전트가 끝나는 순간 DONE 이다.
     */
    private static MessageStatus aggregate(List<Message> agents, Message supervisor) {
        boolean agentsSettled = agents.stream().allMatch(m -> m.getStatus().isSettled());
        if (!agentsSettled) {
            return agents.stream().anyMatch(m -> m.getStatus() == MessageStatus.RUNNING)
                    ? MessageStatus.RUNNING
                    : MessageStatus.PENDING;
        }
        if (supervisor == null || supervisor.getStatus().isSettled()) {
            return MessageStatus.DONE;
        }
        return MessageStatus.RUNNING;
    }

    private static TurnStatusResponse.AgentProgress toView(Message message) {
        return new TurnStatusResponse.AgentProgress(
                message.getAgentKey(),
                message.getStatus().name(),
                message.getStatus() == MessageStatus.DONE ? message.getId() : null,
                message.getError());
    }

    /** 총괄은 room.agents 에 없고 2명 이상일 때 붙는다. 저장 규칙과 같은 곳에서 판단한다. */
    private static List<String> participants(Room room) {
        List<String> keys = new ArrayList<>(room.getAgents().stream()
                .map(RoomAgent::agentKey)
                .toList());
        if (keys.size() >= 2) {
            keys.add(AgentType.SUPERVISOR.key());
        }
        return keys;
    }

    private static Map<String, Map<String, Object>> configsOf(Room room) {
        Map<String, Map<String, Object>> configs = new LinkedHashMap<>();
        room.getAgents().forEach(agent -> configs.put(agent.agentKey(), agent.config()));
        return configs;
    }

    /** 문항 하나만 지정하면 그 문항만, 없으면 자소서 전체를 본다. */
    private List<CoverLetterItem> targetItems(Room room, Long coverLetterItemId) {
        List<CoverLetterItem> items =
                coverLetterItemRepository.findByCoverLetterIdOrderBySeqAsc(room.getCoverLetterId());
        if (coverLetterItemId != null) {
            items = items.stream().filter(item -> item.getId().equals(coverLetterItemId)).toList();
            if (items.isEmpty()) {
                throw new BusinessException(ErrorCode.INVALID_PARAMETER,
                        "이 자소서의 문항이 아닙니다: " + coverLetterItemId);
            }
        }
        if (items.isEmpty()) {
            throw new BusinessException(ErrorCode.INVALID_PARAMETER, "자소서에 문항이 없습니다.");
        }
        return items;
    }

    /** 프롬프트로 도는 에이전트가 읽는 본문. */
    private static String joinedText(List<CoverLetterItem> items) {
        return items.stream()
                .map(item -> "문항 %d. %s%n답변: %s".formatted(
                        item.getSeq(), item.getQuestion(), item.getAnswer()))
                .collect(Collectors.joining("\n\n"));
    }

    /** 포지션·글쓰기 API 가 문항과 답변을 따로 받으므로 조각째로도 싣는다. */
    private static List<TurnContext.CoverLetterPart> partsOf(List<CoverLetterItem> items) {
        return items.stream()
                .map(item -> new TurnContext.CoverLetterPart(
                        item.getSeq(), item.getQuestion(), item.getAnswer(), item.getCharLimit()))
                .toList();
    }

    private Room ownedRoom(Long userId, Long roomId) {
        return roomRepository.findByIdAndUserId(roomId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ROOM_NOT_FOUND,
                        "검토 방을 찾을 수 없습니다: " + roomId));
    }
}

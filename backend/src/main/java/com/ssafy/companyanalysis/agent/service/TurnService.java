package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.ai.SupervisorClient;
import com.ssafy.companyanalysis.agent.domain.AgentType;
import com.ssafy.companyanalysis.agent.domain.JobContext;
import com.ssafy.companyanalysis.agent.domain.Message;
import com.ssafy.companyanalysis.agent.domain.MessageRole;
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
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * 발화를 받아 턴을 시작하고 진행 상황을 알려준다.
 *
 * <p>발화는 결과를 기다리지 않고 turnId 만 돌려준다. 담당 여럿이 돌고 총괄이 종합하기까지
 * 1분을 넘겨 연결이 끊긴다.
 */
@Service
public class TurnService {

    private static final List<MessageStatus> UNFINISHED =
            List.of(MessageStatus.PENDING, MessageStatus.RUNNING);

    /** AI 총괄에 실어 보낼 지난 대화 길이. 명세가 정한 상한이다. */
    private static final int CONVERSATION_LIMIT = 20;

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
     * 발화를 저장하고 담당 자리를 만든 뒤 실행을 띄운다.
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
        String content = request.content().trim();
        TurnContext context = contextOf(room, items, content);

        List<String> agentKeys = participants(room, context);
        if (agentKeys.isEmpty()) {
            throw new BusinessException(ErrorCode.INVALID_PARAMETER,
                    "검토할 자소서 답변이 없습니다. 문항을 먼저 작성해 주세요.");
        }

        Message userMessage = messageRepository.save(Message.fromUser(roomId, content));
        List<Message> slots = agentKeys.stream()
                .map(key -> Message.pendingAgent(roomId, userMessage.getId(), key))
                .toList();
        messageRepository.saveAll(slots);

        turnExecutor.runTurn(userMessage.getId(), context);

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
     * 턴 하나가 볼 재료를 모은다.
     *
     * <p>방에 붙은 공고는 여기서 한 번 확인한다. 분석이 사라졌으면 공고 없는 방으로 본다 —
     * 없는 식별자를 AI 에 넘기면 채용공고·뉴스 담당이 404 로 떨어진다.
     */
    private TurnContext contextOf(Room room, List<CoverLetterItem> items, String content) {
        Optional<JobContext> jobContext = room.getJobContextId() == null
                ? Optional.empty()
                : jobContextRepository.findById(room.getJobContextId());

        return new TurnContext(
                partsOf(items),
                content,
                jobContext.map(JobContext::getContextId).orElse(null),
                jobContext.map(JobContext::getPositionName).orElse(null),
                conversationOf(room.getId()),
                configsOf(room));
    }

    /**
     * AI 총괄은 대화를 저장하지 않는다. 방의 지난 발화를 매번 통째로 실어 보내야 "아까 그
     * 문단" 같은 말이 통한다. 실패했거나 아직 도는 자리는 보낼 내용이 없어 뺀다.
     */
    private List<SupervisorClient.Turn> conversationOf(Long roomId) {
        List<Message> recent = messageRepository.findPage(
                roomId, null, PageRequest.of(0, CONVERSATION_LIMIT));
        return recent.stream()
                .filter(message -> message.getStatus() == MessageStatus.DONE)
                .filter(message -> message.getContent() != null && !message.getContent().isBlank())
                .sorted(Comparator.comparing(Message::getId))
                .map(message -> new SupervisorClient.Turn(
                        String.valueOf(message.getId()),
                        message.getRole() == MessageRole.USER ? "USER" : "ASSISTANT",
                        message.getContent()))
                .toList();
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
     * 한 담당이 실패해도 턴은 실패가 아니다. 전원이 끝났는데 총괄이 아직이면 SUPERVISING,
     * 총괄까지 끝나면 DONE 이다. 총괄이 없는 전담 방은 담당이 끝나는 순간 DONE 이다.
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

    /**
     * 이 턴에 자리를 만들 담당.
     *
     * <p>방에서 고른 담당으로 거르지 않는다. 재료가 있는 담당을 전부 총괄에게 넘기고 무엇을
     * 돌릴지는 총괄의 계획이 정한다. 기업 RAG 담당만 아직 백엔드가 맡고 있어 방에서 고른
     * 경우에만 자리를 만든다.
     *
     * <p>총괄은 {@code room.agents} 에 없고 담당이 2명 이상일 때 붙는다 — 혼자 있는 방에는
     * 조정할 것이 없다.
     */
    private static List<String> participants(Room room, TurnContext context) {
        List<String> keys = new ArrayList<>(AgentContexts.of(context).agentKeys());
        boolean companyPicked = room.getAgents().stream()
                .map(RoomAgent::agentKey)
                .anyMatch(AgentType.COMPANY.key()::equals);
        if (companyPicked) {
            keys.add(AgentType.COMPANY.key());
        }
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

    /** 총괄은 문항과 답변을 따로 받는다. 문항 하나짜리 턴만 글쓰기 첨삭까지 간다. */
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

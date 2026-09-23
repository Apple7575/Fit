package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.ai.SupervisorClient;
import com.ssafy.companyanalysis.agent.config.AgentCatalogProperties;
import com.ssafy.companyanalysis.agent.domain.AgentType;
import com.ssafy.companyanalysis.agent.domain.JobContext;
import com.ssafy.companyanalysis.agent.domain.Message;
import com.ssafy.companyanalysis.agent.domain.MessageRole;
import com.ssafy.companyanalysis.agent.domain.MessageStatus;
import com.ssafy.companyanalysis.agent.domain.Room;
import com.ssafy.companyanalysis.agent.dto.MessageSendRequest;
import com.ssafy.companyanalysis.agent.dto.TurnStartedResponse;
import com.ssafy.companyanalysis.agent.dto.TurnStatusResponse;
import com.ssafy.companyanalysis.agent.policy.AgentInputPolicy;
import com.ssafy.companyanalysis.agent.policy.InputSource;
import com.ssafy.companyanalysis.agent.policy.PolicyDecision;
import com.ssafy.companyanalysis.agent.repository.JobContextRepository;
import com.ssafy.companyanalysis.agent.repository.MessageRepository;
import com.ssafy.companyanalysis.agent.repository.RoomRepository;
import com.ssafy.companyanalysis.coverletter.domain.CoverLetterItem;
import com.ssafy.companyanalysis.coverletter.repository.CoverLetterItemRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionTemplate;

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

    /**
     * 사용자가 묻기 전에 도는 검토에 쓸 지시문.
     *
     * <p>대화에는 남기지 않는다. 사용자가 한 말이 아니라 총괄에게 시킬 일이기 때문이다.
     */
    private static final String AUTO_REVIEW_INSTRUCTION =
            "이 자소서를 담당별 관점에서 처음부터 검토해 주세요.";

    /** 한도에 걸려 검토를 시작하지 못했을 때 자리에 남기는 말. */
    private static final String AUTO_REVIEW_DEFERRED =
            "요청이 많아 자동 검토를 시작하지 못했습니다. 잠시 후 이 방을 다시 열어 주세요.";

    private final RoomRepository roomRepository;
    private final MessageRepository messageRepository;
    private final JobContextRepository jobContextRepository;
    private final CoverLetterItemRepository coverLetterItemRepository;
    private final TurnExecutor turnExecutor;
    private final AnalysisRateLimiter rateLimiter;
    private final AgentCatalogProperties properties;
    private final AgentInputPolicy inputPolicy;
    private final TransactionTemplate transactionTemplate;

    public TurnService(RoomRepository roomRepository,
                       MessageRepository messageRepository,
                       JobContextRepository jobContextRepository,
                       CoverLetterItemRepository coverLetterItemRepository,
                       TurnExecutor turnExecutor,
                       AnalysisRateLimiter rateLimiter,
                       AgentCatalogProperties properties,
                       AgentInputPolicy inputPolicy,
                       PlatformTransactionManager transactionManager) {
        this.roomRepository = roomRepository;
        this.messageRepository = messageRepository;
        this.jobContextRepository = jobContextRepository;
        this.coverLetterItemRepository = coverLetterItemRepository;
        this.turnExecutor = turnExecutor;
        this.rateLimiter = rateLimiter;
        this.properties = properties;
        this.inputPolicy = inputPolicy;
        this.transactionTemplate = new TransactionTemplate(transactionManager);
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

        String content = request.content().trim();
        PolicyDecision policyDecision = inputPolicy.evaluate(content, InputSource.CHAT);
        if (!policyDecision.allowsExecution()) {
            List<String> agentKeys = refusalParticipants(room);
            if (agentKeys.isEmpty()) {
                throw new BusinessException(ErrorCode.INVALID_PARAMETER, "이 방에서 사용할 수 있는 담당이 없습니다.");
            }
            OpenedTurn refused = openRefusedTurn(roomId, agentKeys, content, policyDecision.reply());
            return refusedResponse(refused);
        }

        List<CoverLetterItem> items = targetItems(room, request.coverLetterItemId());
        TurnContext context = contextOf(room, items, content, request.writingReview());

        AgentContexts.Request plan = AgentContexts.of(context);
        List<String> agentKeys = participants(plan);
        if (agentKeys.isEmpty()) {
            // 무엇을 채우면 되는지 말한다. 담당마다 필요한 것이 달라 한 문장으로 덮을 수 없다.
            throw new BusinessException(ErrorCode.INVALID_PARAMETER, plan.blockedReason());
        }

        // 위험하거나 규칙을 뚫으려는 발화는 AI 를 부르지 않고 바로 거절한다.
        Optional<InputGuard.Verdict> blocked = InputGuard.screen(content);
        if (blocked.isPresent()) {
            OpenedTurn refused = openRefusedTurn(roomId, agentKeys, content, blocked.get().reply());
            return refusedResponse(refused);
        }

        OpenedTurn turn = openTurn(roomId, agentKeys, content);

        turnExecutor.runTurn(turn.rootId(), context);

        return new TurnStartedResponse(
                turn.rootId(),
                turn.rootId(),
                MessageStatus.PENDING.name(),
                turn.slots().stream()
                        .map(slot -> new TurnStartedResponse.AgentSlot(
                                slot.getAgentKey(), slot.getStatus().name()))
                        .toList());
    }

    private TurnStartedResponse refusedResponse(OpenedTurn refused) {
        return new TurnStartedResponse(
                refused.rootId(),
                refused.rootId(),
                MessageStatus.DONE.name(),
                refused.slots().stream()
                        .map(slot -> new TurnStartedResponse.AgentSlot(
                                slot.getAgentKey(), slot.getStatus().name()))
                        .toList());
    }

    private List<String> refusalParticipants(Room room) {
        List<String> keys = new ArrayList<>(room.getAgents().stream()
                .filter(agent -> properties.isAgentVisible(agent.agentKey()))
                .map(agent -> agent.agentKey())
                .toList());
        if (keys.size() >= 2 && !keys.contains(AgentType.SUPERVISOR.key())) {
            keys.add(AgentType.SUPERVISOR.key());
        }
        return keys;
    }

    /** 자동 검토 한 바퀴가 쓸 한도. 방마다가 아니라 바퀴마다 한 장이다. */
    public AutoReviewQuota newAutoReviewQuota(Long userId) {
        return new AutoReviewQuota(rateLimiter, userId);
    }

    /**
     * 자동 검토. 자소서를 받은 방이 사용자가 묻기를 기다리지 않고 한 바퀴 돈다.
     *
     * <p>사용자가 한 말이 없으므로 턴의 뿌리는 내용이 빈 발화다. 하지만 AI 총괄은 지시문 없이는
     * 무엇을 할지 정하지 못하므로 {@link #AUTO_REVIEW_INSTRUCTION} 을 대신 보낸다. 사용자가 하지
     * 않은 말을 대화에 남기지 않으면서 총괄에게는 시킬 일을 주는 것이다.
     *
     * <p>끝날 때까지 기다린다. 부르는 쪽({@link AutoReviewStarter})이 방을 하나씩 차례로
     * 돌리기 위한 것이다.
     *
     * <p>돌 자리가 아니면 조용히 물러난다 — 이미 말이 오간 방이나 아직 답변을 쓰지 않은
     * 자소서가 그렇다. 다만 <b>한도에 걸린 것은 다르다.</b> 그때는 자리를 만들어 안내를 남긴다.
     * 조용히 물러나면 화면에 아무것도 남지 않아 사용자는 기능이 죽은 것으로 읽는다.
     *
     * @param quota 이 바퀴의 한도. 같은 바퀴의 방들이 한 장을 나눠 쓴다
     */
    public void autoReview(Long userId, Long roomId, AutoReviewQuota quota) {
        Room room = ownedRoom(userId, roomId);
        if (!reviewable(roomId)) {
            return;
        }

        List<CoverLetterItem> items =
                coverLetterItemRepository.findByCoverLetterIdOrderBySeqAsc(room.getCoverLetterId());
        if (items.isEmpty()) {
            return;
        }
        TurnContext context = contextOf(room, items, AUTO_REVIEW_INSTRUCTION);
        // 자동 검토는 사용자가 부른 것이 아니다. 돌 자리가 아니면 조용히 물러난다.
        List<String> agentKeys = participants(AgentContexts.of(context));
        if (agentKeys.isEmpty()) {
            return;
        }

        // 한도는 여기서 처음 센다. 돌릴 방을 실제로 만났을 때라야 한 바퀴를 쓴 것이다.
        if (!quota.allowed()) {
            leaveDeferredNotice(roomId, agentKeys);
            return;
        }

        OpenedTurn turn = openTurn(roomId, agentKeys, null);

        turnExecutor.runTurnNow(turn.rootId(), context);
    }

    /**
     * 자동 검토를 돌려도 되는 방인지 본다. 안내만 남은 방이면 안내를 지우고 자리를 비워 준다.
     *
     * <p>안내를 그냥 두면 그 방은 "말이 오간 방" 이 되어 영영 자동 검토를 못 받는다. 한도가
     * 풀린 뒤에 다시 열었을 때 검토가 도는 것이 사용자가 기대하는 바다.
     */
    private boolean reviewable(Long roomId) {
        long total = messageRepository.countByRoomId(roomId);
        if (total == 0) {
            return true;
        }
        Message notice = messageRepository.findFirstByRoomIdAndRoleAndStatus(
                roomId, MessageRole.USER, MessageStatus.FAILED).orElse(null);
        if (notice == null) {
            return false;
        }
        List<Message> slots = messageRepository.findByParentMessageIdOrderByIdAsc(notice.getId());
        // 안내 말고 다른 말이 오간 방이면 건드리지 않는다. 사용자가 쓰고 있는 방이다.
        if (total != slots.size() + 1L) {
            return false;
        }
        transactionTemplate.executeWithoutResult(status -> {
            messageRepository.deleteAll(slots);
            messageRepository.delete(notice);
        });
        return true;
    }

    /**
     * 검토를 시작하지 못했다고 자리마다 적어 둔다.
     *
     * <p>실패한 자리로 남기는 이유는 화면이 이미 그 모양을 그릴 줄 알기 때문이다. 자리를
     * 안 만들면 빈 방이 되고, 빈 방은 30초쯤 기다리다 화면이 갱신을 포기한다.
     */
    private void leaveDeferredNotice(Long roomId, List<String> agentKeys) {
        transactionTemplate.executeWithoutResult(status -> {
            Message root = messageRepository.save(Message.deferredAutoReview(roomId));
            List<Message> slots = agentKeys.stream()
                    .map(key -> Message.pendingAgent(roomId, root.getId(), key))
                    .toList();
            slots.forEach(slot -> slot.fail(AUTO_REVIEW_DEFERRED));
            messageRepository.saveAll(slots);
        });
    }

    /** 턴 하나를 여는 데 쓴 행들. 뿌리 발화 하나와 담당마다의 빈 답변 자리. */
    private record OpenedTurn(Long rootId, List<Message> slots) {
    }

    /**
     * 턴의 뿌리와 담당별 답변 자리를 한꺼번에 만든다.
     *
     * <p>둘을 한 트랜잭션에 묶는다. 따로 커밋하면 그 사이에 대화를 읽은 화면이 뿌리만 보게 되는데,
     * 뿌리는 만들어지는 즉시 끝난 상태라 화면은 그것을 "다 끝난 대화" 로 읽는다. 그러면 뒤이어
     * 들어온 답변을 영영 기다리지 않는다.
     *
     * <p>{@code content} 가 null 이면 자동 검토다 — 사용자가 하지 않은 말을 지어내지 않는다.
     */
    private OpenedTurn openTurn(Long roomId, List<String> agentKeys, String content) {
        return transactionTemplate.execute(status -> {
            Message root = messageRepository.save(content == null
                    ? Message.autoReview(roomId)
                    : Message.fromUser(roomId, content));
            List<Message> slots = agentKeys.stream()
                    .map(key -> Message.pendingAgent(roomId, root.getId(), key))
                    .toList();
            messageRepository.saveAll(slots);
            return new OpenedTurn(root.getId(), slots);
        });
    }

    /**
     * 막은 발화에 답할 자리 하나만 만들고 거절 문구로 바로 닫는다.
     *
     * <p>담당마다 같은 거절을 되풀이하면 말풍선만 늘어난다. 총괄이 있는 방은 총괄이, 전담 방은 그
     * 담당이 한 번 답한다. 턴이 만들어지는 즉시 끝나므로 화면은 기다리지 않는다.
     */
    private OpenedTurn openRefusedTurn(Long roomId, List<String> agentKeys, String content, String reply) {
        String responder = agentKeys.contains(AgentType.SUPERVISOR.key())
                ? AgentType.SUPERVISOR.key()
                : agentKeys.get(0);
        return transactionTemplate.execute(status -> {
            Message root = messageRepository.save(Message.fromUser(roomId, content));
            Message slot = Message.pendingAgent(roomId, root.getId(), responder);
            slot.succeed(reply, List.of(), List.of());
            messageRepository.save(slot);
            return new OpenedTurn(root.getId(), List.of(slot));
        });
    }

    /**
     * 턴 하나가 볼 재료를 모은다.
     *
     * <p>방에 붙은 공고는 여기서 한 번 확인한다. 분석이 사라졌으면 공고 없는 방으로 본다 —
     * 없는 식별자를 AI 에 넘기면 채용공고·뉴스 담당이 404 로 떨어진다.
     */
    private TurnContext contextOf(Room room, List<CoverLetterItem> items, String content) {
        return contextOf(room, items, content, false);
    }

    /** 글쓰기 검토 버튼은 방 설정과 무관하게 글쓰기 담당만 실행할 전용 컨텍스트를 만든다. */
    private TurnContext contextOf(Room room, List<CoverLetterItem> items, String content,
                                  boolean writingReview) {
        Optional<JobContext> jobContext = room.getJobContextId() == null
                ? Optional.empty()
                : jobContextRepository.findById(room.getJobContextId());

        return new TurnContext(
                partsOf(items),
                content,
                jobContext.map(JobContext::getContextId).orElse(null),
                jobContext.map(JobContext::getPositionName).orElse(null),
                conversationOf(room.getId()),
                configsOf(room, writingReview),
                AUTO_REVIEW_INSTRUCTION.equals(content));
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
     * <p>방에서 고른 담당 중 재료가 있는 담당만 자리를 만든다. 거르는 일은 {@link AgentContexts}
     * 가 한다 — 여기서 한 번 더 거르면 두 곳이 어긋날 자리가 생긴다.
     *
     * <p>기업 담당도 예외가 아니다. 전에는 기업 코드가 없어도 자리를 만들어, 30초쯤 뒤 말풍선에
     * "설정을 먼저 채워 주세요" 가 떴다. 자리가 없으면 왜 못 도는지 말할 곳이 없어 만든 우회로였는데,
     * 이제 {@link AgentContexts.Request#blockedReason()} 이 보내기 전에 그 이유를 말한다.
     *
     * <p>총괄은 {@code room.agents} 에 없고 담당이 2명 이상일 때 붙는다 — 혼자 있는 방에는
     * 조정할 것이 없다.
     */
    private List<String> participants(AgentContexts.Request plan) {
        List<String> keys = new ArrayList<>(plan.agentKeys());
        if (keys.size() >= 2) {
            keys.add(AgentType.SUPERVISOR.key());
        }
        return keys;
    }

    /**
     * 방이 고른 담당과 그 설정. 이 map 의 키가 곧 이 턴에 부를 담당 목록이 된다.
     *
     * <p>감춘 담당({@code app.agent.hidden-agents})은 여기서 뺀다. 한 곳만 막으면
     * {@link AgentContexts} 가 컨텍스트를 안 만들고, 말풍선 자리도 안 생기고, AI 요청에도
     * 안 실린다 — 전에 만들어져 그 담당이 붙어 있는 방도 마찬가지다.
     */
    private Map<String, Map<String, Object>> configsOf(Room room) {
        return configsOf(room, false);
    }

    private Map<String, Map<String, Object>> configsOf(Room room, boolean writingReview) {
        Map<String, Map<String, Object>> configs = new LinkedHashMap<>();
        if (writingReview) {
            // 버튼 요청은 다른 담당·총괄이 붙은 방에서도 글쓰기 담당만 실행한다.
            configs.put(AgentType.WRITING.key(), Map.of());
            return configs;
        }
        room.getAgents().stream()
                .filter(agent -> properties.isAgentVisible(agent.agentKey()))
                .forEach(agent -> configs.put(agent.agentKey(), agent.config()));
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

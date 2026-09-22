package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.ai.NewsAnalysisClient;
import com.ssafy.companyanalysis.agent.ai.SupervisorClient;
import com.ssafy.companyanalysis.agent.domain.AgentType;
import com.ssafy.companyanalysis.agent.domain.Message;
import com.ssafy.companyanalysis.agent.repository.MessageRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 한 턴의 AI 담당들을 총괄 API 한 번으로 돌리고 결과를 말풍선 자리에 나눠 담는다.
 *
 * <p>담당을 백엔드가 하나씩 부르지 않는다. 어떤 담당을 돌릴지, 담당끼리 무엇을 주고받을지는
 * AI 총괄이 정한다. 백엔드는 재료를 모아 보내고 돌아온 결과를 자리에 넣는 일만 한다.
 *
 * <p>{@link TurnExecutor} 와 분리한 이유는 자기 빈 안에서 부르면 {@code @Transactional} 이
 * 걸리지 않기 때문이다.
 */
@Component
public class SupervisorTurnRunner {

    private static final Logger log = LoggerFactory.getLogger(SupervisorTurnRunner.class);

    /** 총괄이 고르지 않은 담당의 자리에 남길 말. 실패가 아니라서 자리를 비워 두지 않는다. */
    private static final String NOT_SELECTED = "이번 질문에는 이 관점이 필요하지 않다고 보고 넘어갔습니다.";
    private static final int MAX_REASON = 200;

    private final MessageRepository messageRepository;
    private final SupervisorClient supervisorClient;
    private final NewsAnalysisClient newsClient;

    public SupervisorTurnRunner(MessageRepository messageRepository,
                                SupervisorClient supervisorClient,
                                NewsAnalysisClient newsClient) {
        this.messageRepository = messageRepository;
        this.supervisorClient = supervisorClient;
        this.newsClient = newsClient;
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void run(Long turnId, TurnContext context) {
        List<Message> slots = messageRepository.findByParentMessageIdOrderByIdAsc(turnId);
        Map<String, Message> aiSlots = new LinkedHashMap<>();
        Message supervisorSlot = null;
        for (Message slot : slots) {
            if (AgentType.SUPERVISOR.key().equals(slot.getAgentKey())) {
                supervisorSlot = slot;
            } else if (AgentContexts.AI_AGENTS.contains(slot.getAgentKey())) {
                aiSlots.put(slot.getAgentKey(), slot);
            }
        }
        if (aiSlots.isEmpty()) {
            if (supervisorSlot != null) {
                supervisorSlot.fail("종합할 의견이 없습니다.");
            }
            return;
        }

        aiSlots.values().forEach(Message::markRunning);
        if (supervisorSlot != null) {
            supervisorSlot.markRunning();
        }
        messageRepository.flush();

        try {
            AgentContexts.Request request = AgentContexts.of(context);
            if (request.isNewsOnly()) {
                fillFromNews(aiSlots.get("news"), request, context);
            } else {
                fill(aiSlots, supervisorSlot, request, context);
            }
        } catch (Exception e) {
            log.warn("총괄 실행 실패: turnId={}, reason={}", turnId, e.getMessage());
            String reason = shortReason(e);
            aiSlots.values().forEach(slot -> slot.fail(reason));
            if (supervisorSlot != null) {
                supervisorSlot.fail(reason);
            }
        }
    }

    private void fill(Map<String, Message> aiSlots,
                      Message supervisorSlot,
                      AgentContexts.Request request,
                      TurnContext context) {
        SupervisorClient.Run run = supervisorClient.run(
                context.userMessage(),
                request.documents(),
                context.conversation(),
                request.contexts(),
                request.lead(),
                context.autoReview());

        Map<String, Message> waiting = new LinkedHashMap<>(aiSlots);
        List<Long> answered = new ArrayList<>();
        for (SupervisorClient.AgentResult result : run.agentResults()) {
            Message slot = waiting.remove(result.agent());
            if (slot == null) {
                // 자리를 안 만든 담당이 돌아왔다. 컨텍스트를 안 보냈으면 일어나지 않는다.
                continue;
            }
            if (result.succeeded() && !result.message().isBlank()) {
                slot.succeed(result.message(), result.evidence(), List.of());
                answered.add(slot.getId());
            } else {
                slot.fail(result.error() == null ? "담당이 답을 만들지 못했습니다." : result.error());
            }
        }
        // 컨텍스트는 보냈지만 총괄이 고르지 않은 담당. 실패로 두면 사용자가 장애로 읽는다.
        waiting.values().forEach(slot -> slot.succeed(NOT_SELECTED, List.of(), List.of()));

        if (supervisorSlot == null) {
            return;
        }
        if (run.message().isBlank()) {
            supervisorSlot.fail("총괄이 종합 문구를 만들지 못했습니다.");
        } else {
            supervisorSlot.succeed(run.message(), run.evidence(), answered);
        }
    }

    /**
     * 돌릴 담당이 뉴스뿐인 턴. 총괄을 거치면 계획·종합 모델 호출이 덧붙으므로 뉴스 API 를 바로
     * 부른다. 담당이 하나뿐이라 총괄 자리도 애초에 만들지 않는다.
     */
    private void fillFromNews(Message newsSlot, AgentContexts.Request request, TurnContext context) {
        if (newsSlot == null) {
            return;
        }
        Map<?, ?> newsContext = (Map<?, ?>) request.contexts().get("news");
        NewsAnalysisClient.Analysis analysis = newsClient.analyze(
                context.userMessage(),
                String.valueOf(newsContext.get("job_context_id")),
                String.valueOf(newsContext.get("corp_code")),
                context.conversation());
        newsSlot.succeed(analysis.message(), analysis.evidence(), List.of());
    }

    /** 화면에 그대로 뜨는 문구라 스택트레이스가 아니라 한 줄 사유만 남긴다. */
    private static String shortReason(Exception e) {
        String message = e.getMessage();
        if (message == null || message.isBlank()) {
            return "알 수 없는 이유로 실패했습니다.";
        }
        return message.length() > MAX_REASON ? message.substring(0, MAX_REASON) : message;
    }
}

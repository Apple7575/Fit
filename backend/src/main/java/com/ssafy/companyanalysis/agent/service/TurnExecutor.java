package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.domain.AgentType;
import com.ssafy.companyanalysis.agent.domain.Message;
import com.ssafy.companyanalysis.agent.repository.MessageRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;

/**
 * 한 턴을 끝까지 돌린다.
 *
 * <p>채용공고·포지션·뉴스·글쓰기 담당과 총괄은 AI 총괄 API 한 번으로 함께 끝난다. 담당을 고르고
 * 서로 위임시키는 일이 AI 쪽에 있어서 백엔드가 나눠 부를 이유가 없다.
 *
 * <p>기업 RAG 담당만 아직 백엔드에 남아 있어 따로 돌린다(S15P21A504-132). 총괄 호출과 나란히
 * 가되 서로 기다리지 않는다 — 한쪽이 실패해도 다른 쪽 자리는 채워져야 한다. 다만 기업 담당의
 * 의견은 AI 총괄의 종합에 들어가지 않는다.
 */
@Component
public class TurnExecutor {

    private static final Logger log = LoggerFactory.getLogger(TurnExecutor.class);

    private final MessageRepository messageRepository;
    private final AgentTaskRunner agentTaskRunner;
    private final SupervisorTurnRunner supervisorTurnRunner;
    private final Executor agentTaskExecutor;

    public TurnExecutor(MessageRepository messageRepository,
                        AgentTaskRunner agentTaskRunner,
                        SupervisorTurnRunner supervisorTurnRunner,
                        @Qualifier("agentTaskExecutor") Executor agentTaskExecutor) {
        this.messageRepository = messageRepository;
        this.agentTaskRunner = agentTaskRunner;
        this.supervisorTurnRunner = supervisorTurnRunner;
        this.agentTaskExecutor = agentTaskExecutor;
    }

    /** 턴 시작. 호출한 요청은 여기서 기다리지 않는다(발화는 202 로 바로 돌아간다). */
    public void runTurn(Long turnId, TurnContext context) {
        agentTaskExecutor.execute(() -> {
            try {
                runLocalAgentsAndSupervisor(turnId, context);
            } catch (Exception e) {
                log.error("턴 실행이 중단됐다: turnId={}", turnId, e);
            }
        });
    }

    private void runLocalAgentsAndSupervisor(Long turnId, TurnContext context) {
        List<Message> slots = messageRepository.findByParentMessageIdOrderByIdAsc(turnId);

        CompletableFuture<Void> local = CompletableFuture.allOf(slots.stream()
                .filter(slot -> AgentType.COMPANY.key().equals(slot.getAgentKey()))
                .map(slot -> CompletableFuture.runAsync(
                        () -> agentTaskRunner.run(slot.getId(), context), agentTaskExecutor))
                .toArray(CompletableFuture[]::new));

        supervisorTurnRunner.run(turnId, context);
        local.join();
    }
}

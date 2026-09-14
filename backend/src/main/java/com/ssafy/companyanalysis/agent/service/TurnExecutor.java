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
 * 한 턴을 끝까지 돌린다. 참여 에이전트를 병렬로 실행하고, 전원이 끝나면 총괄을 돌린다.
 *
 * <p>2단계인 이유는 총괄이 다른 에이전트의 결과를 받아 종합하기 때문이다. 한 에이전트가
 * 실패해도 기다렸다가 나머지 결과로 총괄을 돌린다 — 뉴스 하나 못 가져왔다고 화면이 통째로
 * 비면 안 된다.
 */
@Component
public class TurnExecutor {

    private static final Logger log = LoggerFactory.getLogger(TurnExecutor.class);

    private final MessageRepository messageRepository;
    private final AgentTaskRunner agentTaskRunner;
    private final SupervisorRunner supervisorRunner;
    private final Executor agentTaskExecutor;

    public TurnExecutor(MessageRepository messageRepository,
                        AgentTaskRunner agentTaskRunner,
                        SupervisorRunner supervisorRunner,
                        @Qualifier("agentTaskExecutor") Executor agentTaskExecutor) {
        this.messageRepository = messageRepository;
        this.agentTaskRunner = agentTaskRunner;
        this.supervisorRunner = supervisorRunner;
        this.agentTaskExecutor = agentTaskExecutor;
    }

    /** 턴 시작. 호출한 요청은 여기서 기다리지 않는다(발화는 202 로 바로 돌아간다). */
    public void runTurn(Long turnId, TurnContext context) {
        agentTaskExecutor.execute(() -> {
            try {
                runAgentsThenSupervisor(turnId, context);
            } catch (Exception e) {
                log.error("턴 실행이 중단됐다: turnId={}", turnId, e);
            }
        });
    }

    private void runAgentsThenSupervisor(Long turnId, TurnContext context) {
        List<Message> slots = messageRepository.findByParentMessageIdOrderByIdAsc(turnId);

        List<CompletableFuture<Void>> running = slots.stream()
                .filter(slot -> !AgentType.SUPERVISOR.key().equals(slot.getAgentKey()))
                .map(slot -> CompletableFuture.runAsync(
                        () -> agentTaskRunner.run(slot.getId(), context), agentTaskExecutor))
                .toList();
        CompletableFuture.allOf(running.toArray(CompletableFuture[]::new)).join();

        slots.stream()
                .filter(slot -> AgentType.SUPERVISOR.key().equals(slot.getAgentKey()))
                .findFirst()
                .ifPresent(slot -> supervisorRunner.run(slot.getId(), turnId));
    }
}

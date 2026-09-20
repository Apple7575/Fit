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

    /**
     * 턴을 부른 스레드에서 끝까지 돌린다. 자동 검토가 방을 하나씩 차례로 돌 때 쓴다.
     *
     * <p>{@link #runTurn} 과 달리 실행 풀에 이끄는 자리를 만들지 않는다. 방마다 이끄는 자리를
     * 하나씩 잡으면 기업 담당이 앉을 자리가 없어 풀이 서로를 기다리며 멈춘다.
     */
    public void runTurnNow(Long turnId, TurnContext context) {
        runLocalAgentsAndSupervisor(turnId, context);
    }

    /**
     * 기업 담당만 있는 방은 그 담당 API 를 직접 부르고, 담당이 여럿인 방은 총괄에게 맡긴다.
     *
     * <p>전담 방은 그 담당과 둘이 이야기하는 자리다. 총괄을 거치면 왕복만 하나 늘고 종합할
     * 것도 없다 — 뉴스 담당이 이미 같은 이유로 총괄을 우회한다({@code SupervisorTurnRunner}).
     *
     * <p>반대로 담당이 여럿이면 총괄로 보내야 한다. 따로 돌리면 총괄이 기업 담당의 답을 보지
     * 못해 종합에서 빠지고, 기업 담당이 뉴스를 요청해도({@code needs}) 전달되지 않는다.
     */
    private void runLocalAgentsAndSupervisor(Long turnId, TurnContext context) {
        if (!isSoloCompanyRoom(context)) {
            supervisorTurnRunner.run(turnId, context);
            return;
        }

        List<Message> slots = messageRepository.findByParentMessageIdOrderByIdAsc(turnId);
        CompletableFuture<Void> local = CompletableFuture.allOf(slots.stream()
                .filter(slot -> AgentType.COMPANY.key().equals(slot.getAgentKey()))
                .map(slot -> CompletableFuture.runAsync(
                        () -> agentTaskRunner.run(slot.getId(), context), agentTaskExecutor))
                .toArray(CompletableFuture[]::new));
        local.join();
    }

    private static boolean isSoloCompanyRoom(TurnContext context) {
        return context.roomAgentKeys().size() == 1
                && context.roomAgentKeys().contains(AgentType.COMPANY.key());
    }
}

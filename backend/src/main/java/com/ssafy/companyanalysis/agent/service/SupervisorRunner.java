package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.ai.AgentLlmClient;
import com.ssafy.companyanalysis.agent.ai.AgentPrompt;
import com.ssafy.companyanalysis.agent.domain.AgentType;
import com.ssafy.companyanalysis.agent.domain.Message;
import com.ssafy.companyanalysis.agent.domain.MessageStatus;
import com.ssafy.companyanalysis.agent.repository.MessageRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.Collectors;

/**
 * 다른 에이전트가 전부 끝난 뒤 마지막에 도는 총괄.
 *
 * <p>{@link TurnExecutor} 와 분리한 이유는 자기 빈 안에서 부르면 {@code @Transactional} 이
 * 걸리지 않기 때문이다.
 */
@Component
public class SupervisorRunner {

    private static final Logger log = LoggerFactory.getLogger(SupervisorRunner.class);

    private final MessageRepository messageRepository;
    private final AgentLlmClient llmClient;

    public SupervisorRunner(MessageRepository messageRepository, AgentLlmClient llmClient) {
        this.messageRepository = messageRepository;
        this.llmClient = llmClient;
    }

    /**
     * 실제로 답한 에이전트의 말만 보고 종합한다. 종합에 쓴 메시지 id 를 basedOn 으로 남겨
     * 화면이 근거 칩으로 연결할 수 있게 한다.
     */
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void run(Long supervisorMessageId, Long turnId) {
        Message supervisor = messageRepository.findById(supervisorMessageId).orElse(null);
        if (supervisor == null) {
            return;
        }
        supervisor.markRunning();
        messageRepository.saveAndFlush(supervisor);

        List<Message> done = messageRepository.findByParentMessageIdOrderByIdAsc(turnId).stream()
                .filter(m -> !m.getId().equals(supervisorMessageId))
                .filter(m -> m.getStatus() == MessageStatus.DONE)
                .toList();

        if (done.isEmpty()) {
            supervisor.fail("종합할 의견이 없습니다. 모든 에이전트가 답하지 못했습니다.");
            return;
        }

        try {
            String peers = done.stream()
                    .map(m -> "[" + displayName(m.getAgentKey()) + "]\n" + m.getContent())
                    .collect(Collectors.joining("\n\n"));
            supervisor.succeed(
                    llmClient.generate(AgentPrompt.systemInstruction(AgentType.SUPERVISOR), peers),
                    List.of(),
                    done.stream().map(Message::getId).toList());
        } catch (Exception e) {
            log.warn("총괄 실행 실패: turnId={}, reason={}", turnId, e.getMessage());
            supervisor.fail(e.getMessage() == null ? "총괄 종합에 실패했습니다." : e.getMessage());
        }
    }

    private static String displayName(String agentKey) {
        return AgentType.from(agentKey).map(AgentType::displayName).orElse(agentKey);
    }
}

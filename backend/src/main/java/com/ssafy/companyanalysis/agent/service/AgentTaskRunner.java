package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.domain.AgentType;
import com.ssafy.companyanalysis.agent.domain.Message;
import com.ssafy.companyanalysis.agent.repository.MessageRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

/**
 * 백엔드에 남은 담당 하나를 실행해 자기 메시지를 채운다.
 *
 * <p>채용공고·포지션·뉴스·글쓰기는 AI 총괄이 맡는다({@link SupervisorTurnRunner}). 여기로 오는
 * 것은 기업 RAG 담당뿐이고, 볼 Vector DB 가 아직 없어 실행 직전에 걸러진다(S15P21A504-132).
 * 자료 없이 프롬프트만 돌리면 모델이 본 척 지어내기 때문이다.
 *
 * <p>한 번의 실행이 한 트랜잭션이다. 실패해도 그 메시지만 FAILED 로 남기고 예외를 삼킨다.
 * 턴 전체는 계속 간다.
 */
@Component
public class AgentTaskRunner {

    private static final Logger log = LoggerFactory.getLogger(AgentTaskRunner.class);

    private final MessageRepository messageRepository;

    public AgentTaskRunner(MessageRepository messageRepository) {
        this.messageRepository = messageRepository;
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void run(Long messageId, TurnContext context) {
        Message message = messageRepository.findById(messageId).orElse(null);
        if (message == null) {
            return;
        }
        message.markRunning();
        messageRepository.saveAndFlush(message);

        try {
            AgentType type = AgentType.from(message.getAgentKey())
                    .orElseThrow(() -> new IllegalStateException("모르는 에이전트: " + message.getAgentKey()));
            if (type != AgentType.COMPANY) {
                throw new IllegalStateException("AI 총괄이 맡은 에이전트다: " + type.key());
            }
            if (!type.isConfigured(context.configOf(type))) {
                // 이름 뒤에 "에이전트" 를 붙여야 조사가 자연스럽다("담당 가" → "담당 에이전트가").
                message.fail(type.displayName() + " 에이전트 설정을 먼저 채워 주세요.");
                return;
            }
            message.fail(type.displayName() + " 에이전트가 볼 자료가 아직 준비되지 않았습니다.");
        } catch (Exception e) {
            log.warn("에이전트 실행 실패: messageId={}, agent={}, reason={}",
                    messageId, message.getAgentKey(), e.getMessage());
            message.fail("지금은 이 에이전트를 쓸 수 없습니다.");
        }
    }
}

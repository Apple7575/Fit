package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.ai.CompanyAnalysisClient;
import com.ssafy.companyanalysis.agent.domain.AgentType;
import com.ssafy.companyanalysis.agent.domain.Message;
import com.ssafy.companyanalysis.agent.repository.MessageRepository;

import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

/**
 * 백엔드에 남은 담당 하나를 실행해 자기 메시지를 채운다.
 *
 * <p>채용공고·포지션·뉴스·글쓰기는 AI 총괄이 맡는다({@link SupervisorTurnRunner}). 여기로 오는
 * 것은 기업 RAG 담당뿐이고, 무상태 대화 API 를 직접 부른다({@link CompanyAnalysisClient}).
 * 담당 하나뿐인 방에 총괄을 거치면 왕복이 하나 더 붙는다 — 뉴스 담당과 같은 이유다.
 *
 * <p>한 번의 실행이 한 트랜잭션이다. 실패해도 그 메시지만 FAILED 로 남기고 예외를 삼킨다.
 * 턴 전체는 계속 간다.
 */
@Component
public class AgentTaskRunner {

    private static final Logger log = LoggerFactory.getLogger(AgentTaskRunner.class);

    private final MessageRepository messageRepository;
    private final CompanyAnalysisClient companyAnalysisClient;

    public AgentTaskRunner(MessageRepository messageRepository,
                           CompanyAnalysisClient companyAnalysisClient) {
        this.messageRepository = messageRepository;
        this.companyAnalysisClient = companyAnalysisClient;
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
            String corpCode = firstCorpCode(context.configOf(type));
            if (corpCode == null) {
                message.fail(type.displayName() + " 에이전트 설정의 기업 코드가 올바르지 않습니다.");
                return;
            }
            CompanyAnalysisClient.Answer answer = companyAnalysisClient.answer(
                    context.userMessage(), corpCode, context.jobContextId(), context.conversation());
            message.succeed(answer.message(), answer.evidence(), List.of());
        } catch (Exception e) {
            log.warn("에이전트 실행 실패: messageId={}, agent={}, reason={}",
                    messageId, message.getAgentKey(), e.getMessage());
            message.fail("지금은 이 에이전트를 쓸 수 없습니다.");
        }
    }

    /**
     * 방은 기업을 여러 개 고를 수 있지만 담당은 한 번에 하나만 본다. 첫 기업을 쓴다.
     *
     * <p>여덟 자리 숫자가 아니면 null 이다. AI 쪽이 형식을 먼저 검사해 422 로 되돌리는데,
     * 그러면 화면에 원인을 알 수 없는 실패로 남는다.
     */
    private static String firstCorpCode(java.util.Map<String, Object> config) {
        if (!(config.get("corpCodes") instanceof java.util.Collection<?> raw)) {
            return null;
        }
        return raw.stream()
                .filter(java.lang.String.class::isInstance)
                .map(java.lang.String.class::cast)
                .map(String::trim)
                .filter(code -> code.matches("[0-9]{8}"))
                .findFirst()
                .orElse(null);
    }
}

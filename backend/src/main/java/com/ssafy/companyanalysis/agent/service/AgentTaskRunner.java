package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.ai.AgentLlmClient;
import com.ssafy.companyanalysis.agent.ai.AgentPrompt;
import com.ssafy.companyanalysis.agent.crawl.CompanyNewsDigest;
import com.ssafy.companyanalysis.agent.crawl.JobPostingFetcher;
import com.ssafy.companyanalysis.agent.domain.AgentType;
import com.ssafy.companyanalysis.agent.domain.JobRole;
import com.ssafy.companyanalysis.agent.domain.Message;
import com.ssafy.companyanalysis.agent.repository.MessageRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;

/**
 * 에이전트 하나를 실행해 자기 메시지를 채운다.
 *
 * <p>한 번의 실행이 한 트랜잭션이다. 에이전트가 병렬로 돌기 때문에 서로의 실패에 말려들면
 * 안 된다 — 실패해도 그 메시지만 FAILED 로 남기고 예외를 삼킨다. 턴 전체는 계속 간다.
 */
@Component
public class AgentTaskRunner {

    private static final Logger log = LoggerFactory.getLogger(AgentTaskRunner.class);

    private final MessageRepository messageRepository;
    private final AgentLlmClient llmClient;
    private final JobPostingFetcher jobPostingFetcher;
    private final CompanyNewsDigest companyNewsDigest;

    public AgentTaskRunner(MessageRepository messageRepository,
                           AgentLlmClient llmClient,
                           JobPostingFetcher jobPostingFetcher,
                           CompanyNewsDigest companyNewsDigest) {
        this.messageRepository = messageRepository;
        this.llmClient = llmClient;
        this.jobPostingFetcher = jobPostingFetcher;
        this.companyNewsDigest = companyNewsDigest;
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

            if (!type.isConfigured(context.configOf(type))) {
                // 이름 뒤에 "에이전트" 를 붙여야 조사가 자연스럽다("담당 가" → "담당 에이전트가").
                message.fail(type.displayName() + " 에이전트 설정을 먼저 채워 주세요.");
                return;
            }

            if (AgentPrompt.requiresUnbuiltSource(type)) {
                // 자료원이 없는데 프롬프트만 돌리면 모델이 본 척 지어낸다. 아예 돌리지 않는다.
                message.fail(type.displayName() + " 에이전트가 볼 자료가 아직 준비되지 않았습니다.");
                return;
            }

            String userText = buildUserText(type, context);
            message.succeed(llmClient.generate(AgentPrompt.systemInstruction(type), userText),
                    List.of(), List.of());
        } catch (Exception e) {
            log.warn("에이전트 실행 실패: messageId={}, agent={}, reason={}",
                    messageId, message.getAgentKey(), e.getMessage());
            message.fail(shortReason(e));
        }
    }

    private String buildUserText(AgentType type, TurnContext context) {
        StringBuilder text = new StringBuilder();
        if (type == AgentType.POSITION) {
            text.append("[지원 직무] ").append(jobRoleLabel(context.configOf(type))).append('\n');
        }
        if (context.userMessage() != null && !context.userMessage().isBlank()) {
            text.append("[사용자 요청] ").append(context.userMessage()).append('\n');
        }
        text.append("[자소서]\n").append(context.coverLetterText());
        return text.toString();
    }

    /** 직무 키만 넘기면 모델이 무엇을 봐야 하는지 모른다. 지식베이스가 덮는 범위를 같이 준다. */
    private String jobRoleLabel(Map<String, Object> config) {
        Object key = config.get("jobRole");
        if (key == null) {
            return "미지정";
        }
        return JobRole.from(String.valueOf(key))
                .map(role -> role.displayName() + " (" + String.join(", ", role.topics()) + ")")
                .orElse(String.valueOf(key));
    }

    /** 화면에 그대로 뜨는 문구라 스택트레이스가 아니라 한 줄 사유만 남긴다. */
    private static String shortReason(Exception e) {
        String message = e.getMessage();
        if (message == null || message.isBlank()) {
            return "알 수 없는 이유로 실패했습니다.";
        }
        return message.length() > 200 ? message.substring(0, 200) : message;
    }
}

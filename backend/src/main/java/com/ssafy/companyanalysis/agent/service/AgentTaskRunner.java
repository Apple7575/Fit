package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.ai.AgentLlmClient;
import com.ssafy.companyanalysis.agent.ai.AgentPrompt;
import com.ssafy.companyanalysis.agent.ai.PositionAnalysisClient;
import com.ssafy.companyanalysis.agent.ai.WritingCoachingClient;
import com.ssafy.companyanalysis.agent.crawl.CompanyNewsDigest;
import com.ssafy.companyanalysis.agent.domain.AgentType;
import com.ssafy.companyanalysis.agent.domain.JobRole;
import com.ssafy.companyanalysis.agent.domain.Message;
import com.ssafy.companyanalysis.agent.repository.MessageRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * 에이전트 하나를 실행해 자기 메시지를 채운다.
 *
 * <p>한 번의 실행이 한 트랜잭션이다. 에이전트가 병렬로 돌기 때문에 서로의 실패에 말려들면
 * 안 된다 — 실패해도 그 메시지만 FAILED 로 남기고 예외를 삼킨다. 턴 전체는 계속 간다.
 *
 * <p>포지션과 글쓰기는 전용 AI API 를 부른다. 나머지는 지시문을 붙여 범용 LLM 으로 돈다.
 */
@Component
public class AgentTaskRunner {

    private static final Logger log = LoggerFactory.getLogger(AgentTaskRunner.class);

    /**
     * 글쓰기는 문항 하나씩 부른다. 문항을 고르지 않은 턴에서 전부 부르면 호출이 문항 수만큼
     * 늘어 한 턴이 몇 분을 넘긴다. 나머지 문항은 문항을 골라 다시 요청하게 안내한다.
     */
    private static final int WRITING_ITEM_LIMIT = 3;

    /** 사용자가 아무 말 없이 검토만 누른 흐름. 글쓰기 API 는 이번 요청 문구를 반드시 받는다. */
    private static final String DEFAULT_WRITING_REQUEST = "이 초안에서 고칠 부분을 짚어 주세요.";

    private final MessageRepository messageRepository;
    private final AgentLlmClient llmClient;
    private final PositionAnalysisClient positionClient;
    private final WritingCoachingClient writingClient;
    private final CompanyNewsDigest companyNewsDigest;

    public AgentTaskRunner(MessageRepository messageRepository,
                           AgentLlmClient llmClient,
                           PositionAnalysisClient positionClient,
                           WritingCoachingClient writingClient,
                           CompanyNewsDigest companyNewsDigest) {
        this.messageRepository = messageRepository;
        this.llmClient = llmClient;
        this.positionClient = positionClient;
        this.writingClient = writingClient;
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

            if (type == AgentType.JD && !context.hasJobPosting()) {
                message.fail("채용공고를 연결한 방에서만 채용공고 담당을 쓸 수 있습니다.");
                return;
            }

            message.succeed(reply(type, context), List.of(), List.of());
        } catch (Exception e) {
            log.warn("에이전트 실행 실패: messageId={}, agent={}, reason={}",
                    messageId, message.getAgentKey(), e.getMessage());
            message.fail(shortReason(e));
        }
    }

    private String reply(AgentType type, TurnContext context) {
        return switch (type) {
            case POSITION -> positionReply(context);
            case WRITING -> writingReply(context);
            default -> llmClient.generate(
                    AgentPrompt.systemInstruction(type), buildUserText(type, context));
        };
    }

    /**
     * 포지션 API 는 자소서 답변을 사실 근거로 받는다. 방에 남긴 사용자의 말은 흐름 문맥이라
     * 근거로 쓰이지 않으므로 conversation 으로만 넘긴다.
     */
    private String positionReply(TurnContext context) {
        Map<String, Object> config = context.configOf(AgentType.POSITION);
        String key = String.valueOf(config.get("jobRole"));
        Optional<JobRole> role = JobRole.from(key);

        List<PositionAnalysisClient.Document> documents = context.answeredParts().stream()
                .map(part -> new PositionAnalysisClient.Document(
                        "cover-letter-item-" + part.seq(), "SELF_INTRO", part.answer()))
                .toList();
        if (documents.isEmpty()) {
            throw new BusinessException(ErrorCode.AI_FAILED, "검토할 자소서 답변이 없습니다.");
        }

        return positionClient.analyze(
                role.map(JobRole::displayName).orElse(key),
                role.map(JobRole::topics).orElse(List.of()),
                documents,
                userTurn(context));
    }

    /** 글쓰기 API 는 문항 하나만 본다. 문항별로 부르고 결과를 한 메시지로 모은다. */
    private String writingReply(TurnContext context) {
        List<TurnContext.CoverLetterPart> answered = context.answeredParts();
        if (answered.isEmpty()) {
            throw new BusinessException(ErrorCode.AI_FAILED, "검토할 자소서 답변이 없습니다.");
        }
        List<TurnContext.CoverLetterPart> targets = answered.stream()
                .limit(WRITING_ITEM_LIMIT)
                .toList();
        String request = context.userMessage() == null || context.userMessage().isBlank()
                ? DEFAULT_WRITING_REQUEST
                : context.userMessage();

        StringBuilder reply = new StringBuilder();
        for (TurnContext.CoverLetterPart part : targets) {
            WritingCoachingClient.Revision revision = writingClient.revise(
                    request, part.question(), part.answer(), part.charLimit(), List.of());
            if (!reply.isEmpty()) {
                reply.append("\n\n");
            }
            reply.append("문항 ").append(part.seq()).append(". ").append(revision.message());
            if (revision.revisedText() != null) {
                // 제안일 뿐이므로 초안으로 자동 승격하지 않는다. 수락은 사용자가 따로 한다.
                reply.append("\n[제안] ").append(revision.revisedText());
            }
        }
        if (answered.size() > targets.size()) {
            reply.append("\n\n한 번에 ").append(WRITING_ITEM_LIMIT)
                    .append("문항까지 봅니다. 나머지는 문항을 골라 다시 요청해 주세요.");
        }
        return reply.toString();
    }

    private static List<PositionAnalysisClient.Turn> userTurn(TurnContext context) {
        if (context.userMessage() == null || context.userMessage().isBlank()) {
            return List.of();
        }
        return List.of(new PositionAnalysisClient.Turn("current", "USER", context.userMessage()));
    }

    /**
     * 에이전트에게 넘길 재료를 붙인다.
     *
     * <p>공고는 방에 붙어 있으면 전원에게 넘긴다. 채용공고 담당만 알면 포지션 담당은 어느 수준을
     * 요구하는지 모르고, 글쓰기 담당은 공고에 쓰인 말투를 모른다.
     */
    private String buildUserText(AgentType type, TurnContext context) {
        StringBuilder text = new StringBuilder();
        if (context.userMessage() != null && !context.userMessage().isBlank()) {
            text.append("[사용자 요청] ").append(context.userMessage()).append("\n");
        }
        if (context.hasJobPosting()) {
            text.append("[채용공고]\n").append(context.jobPostingText()).append("\n\n");
        }
        text.append("[자소서]\n").append(context.coverLetterText());
        return text.toString();
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

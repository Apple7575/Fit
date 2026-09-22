package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.ai.SupervisorClient;
import com.ssafy.companyanalysis.agent.domain.AgentType;

import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 총괄에게 넘길 문서와 담당별 컨텍스트를 만든다.
 *
 * <p>방에서 고른 담당만 넘긴다. 전담 방은 그 담당의 의견만 보러 들어오는 자리다 — 포지션
 * 담당 방을 열었는데 글쓰기 담당과 총괄까지 답하면 방을 나눈 뜻이 없어진다. 총괄 논의 방은
 * 담당을 전부 갖고 있어 이 거르기에 걸리지 않는다.
 *
 * <p>고른 담당 중에서 무엇을 실제로 돌릴지는 그다음 총괄의 계획이 정한다.
 *
 * <p>턴이 시작될 때 자리를 만들 때와 실제로 부를 때 두 번 불린다. 같은 {@link TurnContext} 에
 * 대해 늘 같은 결과가 나와야 자리와 결과가 어긋나지 않는다.
 */
public final class AgentContexts {

    /** AI 총괄이 맡는 담당. 기업 RAG 담당은 아직 총괄이 받지 않아 백엔드에 남아 있다. */
    public static final List<String> AI_AGENTS = List.of("jd", "position", "news", "writing", "company");

    /** 포지션 담당 API 가 이 값만 받는다. */
    private static final String RUBRIC_ID = "experience-depth-v1";
    private static final int MAX_DOCUMENTS = 21;
    private static final int MAX_POSITION_NAME = 200;
    private static final int MAX_QUESTION = 500;
    private static final int MAX_CHAR_LIMIT = 50_000;

    private AgentContexts() {
    }

    public static Request of(TurnContext context) {
        List<TurnContext.CoverLetterPart> answered = context.answeredParts();
        List<SupervisorClient.Document> documents = answered.stream()
                .limit(MAX_DOCUMENTS)
                .map(part -> new SupervisorClient.Document(
                        "cover-letter-item-" + part.seq(), "SELF_INTRO", part.answer()))
                .toList();

        // LinkedHashMap 인 이유는 이 순서가 그대로 화면의 말풍선 순서가 되기 때문이다.
        Map<String, Object> contexts = new LinkedHashMap<>();
        if (context.hasJobContext() && !documents.isEmpty()) {
            contexts.put("jd", Map.of("job_context_id", context.jobContextId()));
        }
        String positionName = positionName(context);
        if (positionName != null && !documents.isEmpty()) {
            contexts.put("position", Map.of(
                    "rubric_id", RUBRIC_ID,
                    "position_context", Map.of(
                            "position_name", trim(positionName, MAX_POSITION_NAME),
                            "priority_requirements", List.of())));
        }
        String corpCode = corpCode(context);
        if (context.hasJobContext() && corpCode != null) {
            contexts.put("news", Map.of(
                    "job_context_id", context.jobContextId(),
                    "corp_code", corpCode));
        }
        // 기업 담당은 공고도 자소서도 없이 돈다 — 공시만 보고 답하기 때문이다. 기업 코드만 있으면 된다.
        if (corpCode != null) {
            Map<String, Object> company = new LinkedHashMap<>();
            company.put("corp_code", corpCode);
            if (context.hasJobContext()) {
                company.put("job_context_id", context.jobContextId());
            }
            contexts.put("company", Map.copyOf(company));
        }
        // 글쓰기 담당은 자소서 문서가 정확히 하나여야 돈다. 문항을 고르지 않은 턴은 분석만 받는다.
        if (documents.size() == 1) {
            TurnContext.CoverLetterPart only = answered.get(0);
            if (only.question() != null && !only.question().isBlank()) {
                contexts.put("writing", Map.of(
                        "question", trim(only.question(), MAX_QUESTION),
                        "char_limit", charLimit(only)));
            }
        }
        // 방이 안 고른 담당은 재료가 있어도 뺀다. 자리를 만들 때와 실제로 부를 때가 같아야
        // 하므로 거르기도 여기 한 곳에 둔다.
        contexts.keySet().retainAll(context.roomAgentKeys());

        return new Request(documents, Map.copyOf(contexts), List.copyOf(contexts.keySet()));
    }

    /** 사용자가 확인해 준 직무명이 먼저다. 비어 있으면 공고에 적힌 직무명을 쓴다. */
    private static String positionName(TurnContext context) {
        Object jobRole = context.configOf(AgentType.POSITION).get("jobRole");
        if (jobRole != null && !String.valueOf(jobRole).isBlank()) {
            return String.valueOf(jobRole);
        }
        return context.jobPositionName() == null || context.jobPositionName().isBlank()
                ? null
                : context.jobPositionName();
    }

    /**
     * 뉴스 담당은 기업 하나만 본다. 방은 여러 기업을 고를 수 있으므로 첫 기업을 쓴다.
     *
     * <p>여덟 자리 숫자가 아니면 아예 넣지 않는다. AI 쪽이 형식을 먼저 검사해 422 로 되돌리는데,
     * 그러면 뉴스 하나 때문에 요청 전체가 거절된다.
     */
    private static String corpCode(TurnContext context) {
        String fromNews = firstCorpCode(context.configOf(AgentType.NEWS));
        return fromNews != null ? fromNews : firstCorpCode(context.configOf(AgentType.COMPANY));
    }

    private static String firstCorpCode(Map<String, Object> config) {
        if (!(config.get("corpCodes") instanceof Collection<?> raw)) {
            return null;
        }
        return raw.stream()
                .map(String::valueOf)
                .filter(code -> code.length() == 8 && code.chars().allMatch(Character::isDigit))
                .findFirst()
                .orElse(null);
    }

    /** 글자 수 제한을 안 적어 둔 문항이 있다. 0 을 그대로 보내면 422 가 돌아온다. */
    private static int charLimit(TurnContext.CoverLetterPart part) {
        int limit = part.charLimit() > 0 ? part.charLimit() : part.answer().length();
        return Math.min(Math.max(limit, 1), MAX_CHAR_LIMIT);
    }

    private static String trim(String value, int limit) {
        return value.length() > limit ? value.substring(0, limit) : value;
    }

    /**
     * @param contexts  총괄 요청의 {@code agent_contexts}
     * @param agentKeys {@code contexts} 의 키를 순서대로. 말풍선 자리를 만들 때 쓴다
     */
    public record Request(List<SupervisorClient.Document> documents,
                          Map<String, Object> contexts,
                          List<String> agentKeys) {

        public boolean isEmpty() {
            return contexts.isEmpty();
        }

        /** 담당이 하나뿐이면 계획 단계를 건너뛴다. 모델 호출이 한 번 줄어든다. */
        public String lead() {
            return agentKeys.size() == 1 ? agentKeys.get(0) : null;
        }

        public boolean isNewsOnly() {
            return agentKeys.size() == 1 && "news".equals(agentKeys.get(0));
        }
    }
}

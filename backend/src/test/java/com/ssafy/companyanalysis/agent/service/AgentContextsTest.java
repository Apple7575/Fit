package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.ai.SupervisorClient;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class AgentContextsTest {

    @Test
    @DisplayName("재료가 있는 담당은 방에서 고르지 않았어도 전부 넘긴다 — 고르는 일은 총괄이 한다")
    void everyFillableAgentIsSentRegardlessOfTheRoomSelection() {
        AgentContexts.Request request = AgentContexts.of(context(
                "ctx-1", "백엔드",
                Map.of("news", Map.of("corpCodes", List.of("00126380"))),
                part(1, "지원동기를 쓰세요", "저는 Spring 기반 API 를 만들었습니다.", 1000)));

        assertThat(request.agentKeys()).containsExactly("jd", "position", "news", "writing");
        assertThat(request.lead()).isNull();
    }

    @Test
    @DisplayName("문항을 하나만 고른 턴에서만 글쓰기 담당이 붙는다 — 자소서 문서가 정확히 하나여야 돈다")
    void writingIsSentOnlyWhenExactlyOneItemIsTargeted() {
        AgentContexts.Request many = AgentContexts.of(context(
                "ctx-1", "백엔드", Map.of(),
                part(1, "문항 1", "답변 1", 500),
                part(2, "문항 2", "답변 2", 500)));

        assertThat(many.agentKeys()).containsExactly("jd", "position");
        assertThat(many.documents()).hasSize(2);
    }

    @Test
    @DisplayName("아직 안 쓴 문항은 문서로 보내지 않는다")
    void unansweredItemsAreLeftOut() {
        AgentContexts.Request request = AgentContexts.of(context(
                "ctx-1", "백엔드", Map.of(),
                part(1, "문항 1", "답변 1", 500),
                part(2, "아직 안 쓴 문항", "   ", 500)));

        assertThat(request.documents())
                .extracting(SupervisorClient.Document::documentId)
                .containsExactly("cover-letter-item-1");
        assertThat(request.agentKeys()).contains("writing");
    }

    @Test
    @DisplayName("공고 없이 연 방은 채용공고·뉴스 담당을 넘기지 않는다")
    void jdAndNewsNeedTheJobContext() {
        AgentContexts.Request request = AgentContexts.of(context(
                null, null,
                Map.of("news", Map.of("corpCodes", List.of("00126380")),
                        "position", Map.of("jobRole", "서버 개발")),
                part(1, "문항 1", "답변 1", 500)));

        assertThat(request.agentKeys()).containsExactly("position", "writing");
    }

    @Test
    @DisplayName("기업코드가 여덟 자리 숫자가 아니면 뉴스를 빼고 보낸다 — 하나 때문에 요청 전체가 거절된다")
    void malformedCorpCodeDropsNewsInsteadOfBreakingTheRequest() {
        AgentContexts.Request request = AgentContexts.of(context(
                "ctx-1", "백엔드",
                Map.of("news", Map.of("corpCodes", List.of("126380"))),
                part(1, "문항 1", "답변 1", 500)));

        assertThat(request.agentKeys()).doesNotContain("news");
    }

    @Test
    @DisplayName("사용자가 확인해 준 직무명이 공고에 적힌 직무명보다 먼저다")
    void configuredJobRoleWinsOverTheJobPosting() {
        AgentContexts.Request request = AgentContexts.of(context(
                "ctx-1", "공고에 적힌 직무",
                Map.of("position", Map.of("jobRole", "서버 개발(Java/Spring)")),
                part(1, "문항 1", "답변 1", 500)));

        Map<?, ?> position = (Map<?, ?>) request.contexts().get("position");
        Map<?, ?> positionContext = (Map<?, ?>) position.get("position_context");
        assertThat(positionContext.get("position_name")).isEqualTo("서버 개발(Java/Spring)");
    }

    @Test
    @DisplayName("글자 수 제한을 안 적어 둔 문항은 쓴 길이를 대신 쓴다 — 0 을 보내면 422 다")
    void missingCharLimitFallsBackToTheDraftLength() {
        AgentContexts.Request request = AgentContexts.of(context(
                null, null, Map.of(), part(1, "문항 1", "열 글자입니다", 0)));

        Map<?, ?> writing = (Map<?, ?>) request.contexts().get("writing");
        assertThat(writing.get("char_limit")).isEqualTo("열 글자입니다".length());
    }

    @Test
    @DisplayName("담당이 하나뿐이면 계획 단계를 건너뛰도록 lead 를 지정한다")
    void aSingleAgentIsCalledAsLead() {
        AgentContexts.Request request = AgentContexts.of(context(
                null, null, Map.of(), part(1, "문항 1", "답변 1", 500)));

        assertThat(request.agentKeys()).containsExactly("writing");
        assertThat(request.lead()).isEqualTo("writing");
        assertThat(request.isNewsOnly()).isFalse();
    }

    @Test
    @DisplayName("돌릴 담당이 뉴스뿐이면 총괄을 거치지 않는다 — 계획·종합 호출이 공짜로 붙는다")
    void newsOnlyTurnsSkipTheSupervisor() {
        AgentContexts.Request request = AgentContexts.of(context(
                "ctx-1", null,
                Map.of("news", Map.of("corpCodes", List.of("00126380"))),
                part(1, "문항 1", "  ", 500)));

        assertThat(request.documents()).isEmpty();
        assertThat(request.agentKeys()).containsExactly("news");
        assertThat(request.isNewsOnly()).isTrue();
    }

    @Test
    @DisplayName("보낼 재료가 하나도 없으면 빈 요청이다 — 부르는 쪽이 턴을 열지 않는다")
    void nothingToSendMeansAnEmptyRequest() {
        AgentContexts.Request request = AgentContexts.of(context(
                null, null, Map.of(), part(1, "문항 1", "   ", 500)));

        assertThat(request.isEmpty()).isTrue();
    }

    private static TurnContext context(String jobContextId,
                                       String jobPositionName,
                                       Map<String, Map<String, Object>> configs,
                                       TurnContext.CoverLetterPart... parts) {
        return new TurnContext(List.of(parts), "봐줘", jobContextId, jobPositionName,
                List.of(), configs);
    }

    private static TurnContext.CoverLetterPart part(int seq, String question, String answer,
                                                    int charLimit) {
        return new TurnContext.CoverLetterPart(seq, question, answer, charLimit);
    }
}

package com.ssafy.companyanalysis.agent.ai;

import com.ssafy.companyanalysis.agent.domain.AgentType;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class AgentPromptTest {

    @Test
    @DisplayName("자료가 모델까지 가지 않는 에이전트는 돌리지 않는다 — 없는 자료를 본 척 지어내기 때문이다")
    void agentsWithoutSourceAreBlocked() {
        assertThat(AgentType.values())
                .filteredOn(AgentPrompt::requiresUnbuiltSource)
                .extracting(AgentType::key)
                .containsExactlyInAnyOrder("company", "jd", "news");
    }

    @Test
    @DisplayName("자소서만 보면 되는 에이전트는 그대로 돈다")
    void agentsReadingOnlyTheCoverLetterStillRun() {
        assertThat(AgentPrompt.requiresUnbuiltSource(AgentType.WRITING)).isFalse();
        assertThat(AgentPrompt.requiresUnbuiltSource(AgentType.POSITION)).isFalse();
        assertThat(AgentPrompt.requiresUnbuiltSource(AgentType.SUPERVISOR)).isFalse();
    }

    @Test
    @DisplayName("막아 둔 에이전트도 지시문은 남겨 둔다 — 자료를 붙일 때 그대로 쓴다")
    void blockedAgentsKeepTheirInstruction() {
        assertThat(AgentPrompt.systemInstruction(AgentType.JD)).contains("채용공고 대조");
        assertThat(AgentPrompt.systemInstruction(AgentType.NEWS)).contains("뉴스·트렌드");
    }
}

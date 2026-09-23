package com.ssafy.companyanalysis.agent.policy;

import org.junit.jupiter.api.Test;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.ObjectMapper;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class AgentInputPolicyTest {

    private final AgentInputPolicy policy = new AgentInputPolicy(new PolicyTextNormalizer());

    @Test
    void sharedAdversarialCorpusMatchesExpectedDecisions() throws Exception {
        Path corpus = Path.of("..", "security", "adversarial-input-cases.json");
        List<Map<String, String>> cases = new ObjectMapper().readValue(
                Files.readString(corpus), new TypeReference<>() {});

        for (Map<String, String> item : cases) {
            PolicyDecision decision = policy.evaluate(
                    item.get("text"), InputSource.valueOf(item.get("source")));

            assertThat(decision.action())
                    .as(item.get("id"))
                    .isEqualTo(PolicyAction.valueOf(item.get("expected")));
        }
    }

    @Test
    void rejectedInputReturnsOneStableUserFacingReply() {
        PolicyDecision decision = policy.evaluate("점심 추천해줘", InputSource.CHAT);

        assertThat(decision.allowsExecution()).isFalse();
        assertThat(decision.reply()).isEqualTo(
                "이 방에서는 자소서와 지원 준비에 관한 질문에만 답할 수 있습니다. "
                        + "자소서나 지원 공고에 대해 물어봐 주세요.");
        assertThat(decision.policyVersion()).isEqualTo("agent-policy-v1");
    }
}

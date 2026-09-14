package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.domain.AgentType;

import java.util.Map;

/**
 * 한 턴을 도는 동안 에이전트들이 함께 보는 재료.
 *
 * <p>턴을 시작할 때 한 번 만들어 넘긴다. 에이전트마다 자소서를 다시 조회하면 같은 내용을
 * 여러 번 읽게 된다.
 *
 * @param coverLetterText 문항과 답변을 붙인 본문
 * @param userMessage     사용자가 방에 남긴 말
 * @param agentConfigs    agentKey 별 설정(기업 선택·직무 선택)
 */
public record TurnContext(String coverLetterText,
                          String userMessage,
                          Map<String, Map<String, Object>> agentConfigs) {

    public Map<String, Object> configOf(AgentType type) {
        return agentConfigs.getOrDefault(type.key(), Map.of());
    }
}

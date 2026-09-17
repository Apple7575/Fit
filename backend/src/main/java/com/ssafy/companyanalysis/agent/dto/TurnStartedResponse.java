package com.ssafy.companyanalysis.agent.dto;

import java.util.List;

/**
 * 발화 접수 결과(202). 결과가 아니라 접수증이다.
 *
 * <p>{@code turnId} 는 방금 저장한 사용자 발화의 id 다 — 턴 테이블을 따로 두지 않는다.
 */
public record TurnStartedResponse(
        Long turnId,
        Long messageId,
        String status,
        List<AgentSlot> agents) {

    public record AgentSlot(String agentKey, String status) {
    }
}

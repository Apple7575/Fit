package com.ssafy.companyanalysis.agent.dto;

import java.util.List;

/**
 * 턴 진행 상황. 화면이 2초 간격으로 이걸 물어 진행 표시를 그린다.
 *
 * <p>{@code status} 는 저장된 값이 아니라 에이전트들의 상태를 모아 계산한 것이다.
 * 한 에이전트가 FAILED 여도 턴은 실패가 아니다.
 */
public record TurnStatusResponse(
        Long turnId,
        String status,
        List<AgentProgress> agents,
        AgentProgress supervisor) {

    /**
     * @param messageId 끝난 경우에만 채운다. 대화 내역에서 그 메시지를 가리킨다
     * @param error     실패 사유. 화면에 그대로 보여준다
     */
    public record AgentProgress(String agentKey, String status, Long messageId, String error) {
    }
}

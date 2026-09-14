package com.ssafy.companyanalysis.agent.domain;

/**
 * 에이전트 답변의 실행 상태.
 *
 * <p>사용자 발화는 만들어지는 즉시 {@link #DONE} 이다. 에이전트 답변은 PENDING 으로 만들어 두고
 * 실행하면서 갱신한다. 한 에이전트가 {@link #FAILED} 여도 턴 전체는 실패가 아니다.
 */
public enum MessageStatus {
    PENDING,
    RUNNING,
    DONE,
    FAILED;

    public boolean isSettled() {
        return this == DONE || this == FAILED;
    }
}

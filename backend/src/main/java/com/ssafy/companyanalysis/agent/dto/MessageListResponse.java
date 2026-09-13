package com.ssafy.companyanalysis.agent.dto;

import com.ssafy.companyanalysis.agent.domain.Evidence;

import java.time.OffsetDateTime;
import java.util.List;

/**
 * 방의 대화 내역. 최신순 커서 페이징이다.
 *
 * <p>{@code nextCursor} 가 null 이면 더 없다.
 */
public record MessageListResponse(List<Message> messages, String nextCursor) {

    /**
     * @param turnId    딸린 사용자 발화의 id. 사용자 발화 자신은 자기 id 가 들어간다
     * @param evidences 기업 RAG·뉴스 담당이 근거로 쓴 자료. 없으면 빈 배열
     * @param basedOn   총괄이 종합에 쓴 메시지 id. 화면이 근거 칩으로 연결한다
     * @param error     실패 사유. 실패한 에이전트도 그 자리에 남는다
     */
    public record Message(
            Long messageId,
            Long turnId,
            String role,
            String agentKey,
            String agentName,
            String content,
            List<Evidence> evidences,
            List<Long> basedOn,
            String status,
            String error,
            OffsetDateTime createdAt) {
    }
}

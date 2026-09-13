package com.ssafy.companyanalysis.agent.dto;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;

/**
 * 검토 방 상세.
 *
 * <p>{@code agents[].config} 는 저장된 값 그대로가 아니라 화면이 쓰기 좋게 채운 것이다.
 * 기업 담당·뉴스 담당의 corpCodes 는 기업명과 ragReady 를 붙인 {@code companies} 로 나간다.
 */
public record RoomResponse(
        Long roomId,
        String title,
        CoverLetterRef coverLetter,
        List<Agent> agents,
        OffsetDateTime createdAt,
        OffsetDateTime lastMessageAt) {

    public record CoverLetterRef(Long id, String title) {
    }

    /**
     * @param auto  사용자가 고른 것이 아니라 서버가 붙인 에이전트(총괄)
     * @param ready 설정이 다 채워져 바로 쓸 수 있는 상태
     */
    public record Agent(
            String agentKey,
            String name,
            boolean auto,
            boolean ready,
            Map<String, Object> config) {
    }
}

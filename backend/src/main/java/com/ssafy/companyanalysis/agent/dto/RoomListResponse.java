package com.ssafy.companyanalysis.agent.dto;

import java.time.OffsetDateTime;
import java.util.List;

/**
 * 사이드바용 방 목록.
 *
 * <p>{@code lastMessagePreview} 와 {@code running} 은 대화 테이블이 생기는
 * S15P21A504-130 에서 채운다. 그 전까지는 각각 null · false 로 나간다 —
 * 필드를 빼면 프론트가 나중에 응답 모양을 다시 맞춰야 한다.
 */
public record RoomListResponse(List<Room> rooms) {

    public record Room(
            Long roomId,
            String title,
            int agentCount,
            String lastMessagePreview,
            OffsetDateTime lastMessageAt,
            boolean running) {
    }
}

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

    /**
     * @param ready 이 방에서 지금 답할 수 있는 담당이 하나라도 있는지. 없으면 화면이 칩을 흐리게 둔다
     * @param need  답할 수 있는 담당이 없을 때 무엇을 채우면 되는지 한 줄. 답할 수 있으면 null
     */
    public record Room(
            Long roomId,
            String title,
            int agentCount,
            String lastMessagePreview,
            OffsetDateTime lastMessageAt,
            boolean running,
            boolean ready,
            String need) {
    }
}

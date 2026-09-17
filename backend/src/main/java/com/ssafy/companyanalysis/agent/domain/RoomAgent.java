package com.ssafy.companyanalysis.agent.domain;

import java.util.Map;

/**
 * 방에 들어온 에이전트 하나와 그 설정. {@code room.agents} JSONB 의 원소다.
 *
 * <p>{@code config} 를 타입 없는 맵으로 두는 이유는 에이전트마다 요구하는 항목이 다르고
 * 에이전트가 늘어날 수 있기 때문이다. 모양 검증은 {@link AgentType#configSchema()} 로 서비스에서 한다.
 */
public record RoomAgent(String agentKey, Map<String, Object> config) {

    public RoomAgent {
        config = config == null ? Map.of() : Map.copyOf(config);
    }

    public static RoomAgent of(AgentType type, Map<String, Object> config) {
        return new RoomAgent(type.key(), config);
    }
}

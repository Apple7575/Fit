package com.ssafy.companyanalysis.agent.dto;

import com.ssafy.companyanalysis.agent.domain.ConfigField;

import java.util.List;
import java.util.Map;

/**
 * 에이전트 카탈로그 응답.
 *
 * <p>{@code configSchema} 는 항목 이름을 키로 하는 객체이며 화면에 나열할 순서를 지킨다.
 */
public record AgentCatalogResponse(List<Agent> agents) {

    public record Agent(
            String agentKey,
            String name,
            String description,
            String dataSource,
            boolean selectable,
            Map<String, ConfigField> configSchema) {
    }
}

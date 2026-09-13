package com.ssafy.companyanalysis.agent.dto;

import jakarta.validation.constraints.NotNull;

import java.util.Map;

/** 방에 들어온 에이전트 하나의 설정 교체(기업 선택 · 직무 선택). */
public record AgentConfigRequest(@NotNull Map<String, Object> config) {
}

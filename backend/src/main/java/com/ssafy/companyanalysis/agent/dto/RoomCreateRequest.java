package com.ssafy.companyanalysis.agent.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.util.List;
import java.util.Map;

/**
 * 검토 방 생성 요청.
 *
 * <p>총괄(supervisor)은 보내지 않는다. 에이전트가 2명 이상이면 서버가 붙인다.
 */
public record RoomCreateRequest(
        @NotNull Long coverLetterId,
        @NotBlank @Size(max = 120) String title,
        @NotEmpty List<AgentSpec> agents) {

    public record AgentSpec(@NotBlank String agentKey, Map<String, Object> config) {
    }
}

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
 *
 * <p>{@code jobContextId} 는 자소서 작성 화면이 채용공고를 확인했을 때만 온다. 공고 없이도
 * 방은 열리므로 선택이다.
 */
public record RoomCreateRequest(
        @NotNull Long coverLetterId,
        @NotBlank @Size(max = 120) String title,
        @Size(max = 80) String jobContextId,
        @NotEmpty List<AgentSpec> agents) {

    public record AgentSpec(@NotBlank String agentKey, Map<String, Object> config) {
    }
}

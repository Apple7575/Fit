package com.ssafy.companyanalysis.agent.dto;

import java.util.List;

/**
 * 지원 직무 목록 응답.
 *
 * <p>{@code ready = false} 는 지식베이스가 아직 없다는 뜻이다. 고르면 포지션 담당이 일반론만
 * 말하므로 화면에서 비활성으로 보여준다. 이때 {@code topics} 는 빈 배열이다 —
 * 덮는 범위가 없는데 있다고 보여줄 수 없다.
 */
public record JobRoleListResponse(List<JobRole> jobRoles) {

    public record JobRole(String key, String name, boolean ready, List<String> topics) {
    }
}

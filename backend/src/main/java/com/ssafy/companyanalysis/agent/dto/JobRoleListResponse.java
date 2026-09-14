package com.ssafy.companyanalysis.agent.dto;

import java.util.List;

/**
 * 지원 직무 목록 응답.
 *
 * <p>{@code ready = false} 는 아직 열지 않은 직무라는 뜻이다(설정으로 정한다). 고를 수 없으므로
 * 화면에서 비활성으로 보여준다. 이때 {@code topics} 는 빈 배열이다 — 못 고르는 직무의 관점을
 * 미리 늘어놓을 이유가 없다.
 */
public record JobRoleListResponse(List<JobRole> jobRoles) {

    public record JobRole(String key, String name, boolean ready, List<String> topics) {
    }
}

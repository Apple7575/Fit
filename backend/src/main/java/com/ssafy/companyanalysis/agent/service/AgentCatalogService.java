package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.config.AgentCatalogProperties;
import com.ssafy.companyanalysis.agent.domain.AgentType;
import com.ssafy.companyanalysis.agent.dto.AgentCatalogResponse;
import com.ssafy.companyanalysis.agent.dto.JobRoleListResponse;
import org.springframework.stereotype.Service;

import java.util.Arrays;
import java.util.List;

/** 에이전트 6종과 지원 직무 목록을 내려준다. 조회뿐이라 저장소를 쓰지 않는다. */
@Service
public class AgentCatalogService {

    private final AgentCatalogProperties properties;

    public AgentCatalogService(AgentCatalogProperties properties) {
        this.properties = properties;
    }

    /** 총괄을 포함해 전부 내려준다. 사용자가 고를 수 있는지는 selectable 로 구분한다. */
    public AgentCatalogResponse listAgents() {
        List<AgentCatalogResponse.Agent> agents = Arrays.stream(AgentType.values())
                .map(type -> new AgentCatalogResponse.Agent(
                        type.key(),
                        type.displayName(),
                        type.description(),
                        type.dataSource(),
                        type.selectable(),
                        type.configSchema()))
                .toList();
        return new AgentCatalogResponse(agents);
    }

    /** 지식베이스가 없는 직무도 목록에는 남긴다. 화면에서 왜 못 고르는지 보여줘야 하기 때문이다. */
    public JobRoleListResponse listJobRoles() {
        List<JobRoleListResponse.JobRole> roles = Arrays.stream(com.ssafy.companyanalysis.agent.domain.JobRole.values())
                .map(role -> {
                    boolean ready = properties.isReady(role);
                    return new JobRoleListResponse.JobRole(
                            role.key(),
                            role.displayName(),
                            ready,
                            ready ? role.topics() : List.of());
                })
                .toList();
        return new JobRoleListResponse(roles);
    }
}

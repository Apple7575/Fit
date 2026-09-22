package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.config.AgentCatalogProperties;
import com.ssafy.companyanalysis.agent.domain.AgentType;
import com.ssafy.companyanalysis.agent.dto.AgentCatalogResponse;
import org.springframework.stereotype.Service;

import java.util.Arrays;
import java.util.List;

/** 에이전트 6종을 내려준다. 조회뿐이라 저장소를 쓰지 않는다. */
@Service
public class AgentCatalogService {

    private final AgentCatalogProperties properties;

    public AgentCatalogService(AgentCatalogProperties properties) {
        this.properties = properties;
    }

    /**
     * 총괄을 포함해 전부 내려준다. 사용자가 고를 수 있는지는 selectable 로 구분한다.
     *
     * <p>잠시 감춘 담당({@code app.agent.hidden-agents})도 목록에는 남기되 selectable 을
     * 내린다. 목록에서 통째로 빼면 그 담당이 붙어 있는 옛 방의 말풍선을 화면이 못 읽는다.
     */
    public AgentCatalogResponse listAgents() {
        List<AgentCatalogResponse.Agent> agents = Arrays.stream(AgentType.values())
                .map(type -> new AgentCatalogResponse.Agent(
                        type.key(),
                        type.displayName(),
                        type.description(),
                        type.dataSource(),
                        type.selectable() && properties.isAgentVisible(type.key()),
                        type.configSchema()))
                .toList();
        return new AgentCatalogResponse(agents);
    }

}

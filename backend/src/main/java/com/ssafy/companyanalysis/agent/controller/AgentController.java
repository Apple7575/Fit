package com.ssafy.companyanalysis.agent.controller;

import com.ssafy.companyanalysis.agent.dto.AgentCatalogResponse;
import com.ssafy.companyanalysis.agent.service.AgentCatalogService;
import com.ssafy.companyanalysis.global.response.ApiResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** 자소서를 검토하는 에이전트 카탈로그. 설정 화면을 그리는 데 쓰므로 로그인 없이 볼 수 있다. */
@RestController
@RequestMapping("/api/agents")
public class AgentController {

    private final AgentCatalogService agentCatalogService;

    public AgentController(AgentCatalogService agentCatalogService) {
        this.agentCatalogService = agentCatalogService;
    }

    @GetMapping
    public ApiResponse<AgentCatalogResponse> agents() {
        return ApiResponse.ok(agentCatalogService.listAgents());
    }
}

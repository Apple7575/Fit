package com.ssafy.companyanalysis.agent.controller;

import com.ssafy.companyanalysis.agent.dto.JobRoleListResponse;
import com.ssafy.companyanalysis.agent.service.AgentCatalogService;
import com.ssafy.companyanalysis.global.response.ApiResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** 포지션 담당 에이전트가 지원하는 직무 목록. */
@RestController
@RequestMapping("/api/job-roles")
public class JobRoleController {

    private final AgentCatalogService agentCatalogService;

    public JobRoleController(AgentCatalogService agentCatalogService) {
        this.agentCatalogService = agentCatalogService;
    }

    @GetMapping
    public ApiResponse<JobRoleListResponse> jobRoles() {
        return ApiResponse.ok(agentCatalogService.listJobRoles());
    }
}

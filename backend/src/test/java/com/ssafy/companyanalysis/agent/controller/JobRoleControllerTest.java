package com.ssafy.companyanalysis.agent.controller;

import com.ssafy.companyanalysis.agent.dto.JobRoleListResponse;
import com.ssafy.companyanalysis.agent.service.AgentCatalogService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.hamcrest.Matchers.hasSize;
import static org.mockito.BDDMockito.given;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(JobRoleController.class)
@AutoConfigureMockMvc(addFilters = false)
class JobRoleControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private AgentCatalogService agentCatalogService;

    @Test
    @DisplayName("직무 목록은 ready 와 topics 를 함께 준다")
    void returnsReadinessAndTopics() throws Exception {
        given(agentCatalogService.listJobRoles()).willReturn(new JobRoleListResponse(List.of(
                new JobRoleListResponse.JobRole("backend", "백엔드", true, List.of("동시성", "분산 락")),
                new JobRoleListResponse.JobRole("data", "데이터", false, List.of()))));

        mockMvc.perform(get("/api/job-roles"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.jobRoles", hasSize(2)))
                .andExpect(jsonPath("$.data.jobRoles[0].key").value("backend"))
                .andExpect(jsonPath("$.data.jobRoles[0].name").value("백엔드"))
                .andExpect(jsonPath("$.data.jobRoles[0].ready").value(true))
                .andExpect(jsonPath("$.data.jobRoles[0].topics", hasSize(2)))
                .andExpect(jsonPath("$.data.jobRoles[1].ready").value(false))
                .andExpect(jsonPath("$.data.jobRoles[1].topics", hasSize(0)))
                .andExpect(jsonPath("$.error").doesNotExist());
    }
}

package com.ssafy.companyanalysis.agent.controller;

import com.ssafy.companyanalysis.agent.domain.ConfigField;
import com.ssafy.companyanalysis.agent.dto.AgentCatalogResponse;
import com.ssafy.companyanalysis.agent.service.AgentCatalogService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.hamcrest.Matchers.hasSize;
import static org.mockito.BDDMockito.given;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(AgentController.class)
@AutoConfigureMockMvc(addFilters = false)
class AgentControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private AgentCatalogService agentCatalogService;

    @Test
    @DisplayName("에이전트 카탈로그는 표준 응답 봉투로 나간다")
    void returnsStandardEnvelope() throws Exception {
        Map<String, ConfigField> companySchema = new LinkedHashMap<>();
        companySchema.put("corpCodes", new ConfigField("array", true, "분석 대상 기업의 corpCode 목록. 복수 선택"));

        given(agentCatalogService.listAgents()).willReturn(new AgentCatalogResponse(List.of(
                new AgentCatalogResponse.Agent("company", "기업 RAG 담당", "기업의 사업 방향에 비추어 본다",
                        "기업별 Vector DB(사업보고서 · IR)", true, companySchema),
                new AgentCatalogResponse.Agent("supervisor", "총괄", "지적을 종합한다",
                        "다른 에이전트의 출력", false, Map.of()))));

        mockMvc.perform(get("/api/agents"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.agents", hasSize(2)))
                .andExpect(jsonPath("$.data.agents[0].agentKey").value("company"))
                .andExpect(jsonPath("$.data.agents[0].name").value("기업 RAG 담당"))
                .andExpect(jsonPath("$.data.agents[0].selectable").value(true))
                .andExpect(jsonPath("$.data.agents[0].configSchema.corpCodes.type").value("array"))
                .andExpect(jsonPath("$.data.agents[0].configSchema.corpCodes.required").value(true))
                .andExpect(jsonPath("$.data.agents[1].selectable").value(false))
                .andExpect(jsonPath("$.error").doesNotExist());
    }

    @Test
    @DisplayName("설정이 없는 에이전트의 configSchema 는 키를 지운 것이 아니라 빈 객체다")
    void emptyConfigSchemaIsStillPresent() throws Exception {
        given(agentCatalogService.listAgents()).willReturn(new AgentCatalogResponse(List.of(
                new AgentCatalogResponse.Agent("writing", "글쓰기 담당", "문장을 교정한다",
                        "자소서 원문", true, Map.of()))));

        mockMvc.perform(get("/api/agents"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.agents[0].configSchema").exists())
                .andExpect(jsonPath("$.data.agents[0].configSchema").isMap());
    }
}

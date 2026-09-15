package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.config.AgentCatalogProperties;
import com.ssafy.companyanalysis.agent.dto.AgentCatalogResponse;
import com.ssafy.companyanalysis.agent.dto.JobRoleListResponse;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class AgentCatalogServiceTest {

    private AgentCatalogService service(String... readyRoles) {
        return new AgentCatalogService(new AgentCatalogProperties(Set.of(readyRoles), Set.of()));
    }

    @Test
    @DisplayName("에이전트는 기획안의 6종을 모두 내려준다")
    void listsAllSixAgents() {
        AgentCatalogResponse response = service().listAgents();

        assertThat(response.agents()).extracting(AgentCatalogResponse.Agent::agentKey)
                .containsExactly("jd", "company", "position", "news", "writing", "supervisor");
    }

    @Test
    @DisplayName("총괄만 고를 수 없다 — 에이전트가 2명 이상일 때 서버가 자동으로 붙이기 때문이다")
    void onlySupervisorIsNotSelectable() {
        AgentCatalogResponse response = service().listAgents();

        assertThat(response.agents())
                .filteredOn(agent -> !agent.selectable())
                .extracting(AgentCatalogResponse.Agent::agentKey)
                .containsExactly("supervisor");
    }

    @Test
    @DisplayName("기업 담당은 corpCodes 를 배열로 필수 요구하고, 포지션 담당은 jobRole 하나를 요구한다")
    void configSchemaDescribesCompanyAndPositionSettings() {
        List<AgentCatalogResponse.Agent> agents = service().listAgents().agents();

        AgentCatalogResponse.Agent company = agents.stream()
                .filter(a -> a.agentKey().equals("company")).findFirst().orElseThrow();
        assertThat(company.configSchema()).containsOnlyKeys("corpCodes");
        assertThat(company.configSchema().get("corpCodes").type()).isEqualTo("array");
        assertThat(company.configSchema().get("corpCodes").required()).isTrue();

        AgentCatalogResponse.Agent position = agents.stream()
                .filter(a -> a.agentKey().equals("position")).findFirst().orElseThrow();
        assertThat(position.configSchema()).containsOnlyKeys("jobRole");
        assertThat(position.configSchema().get("jobRole").type()).isEqualTo("enum");
    }

    @Test
    @DisplayName("글쓰기 담당과 총괄은 설정할 것이 없다")
    void writingAndSupervisorNeedNoConfig() {
        List<AgentCatalogResponse.Agent> agents = service().listAgents().agents();

        assertThat(agents).filteredOn(a -> a.agentKey().equals("writing") || a.agentKey().equals("supervisor"))
                .allSatisfy(agent -> assertThat(agent.configSchema()).isEmpty());
    }

    @Test
    @DisplayName("뉴스 담당이 받는 설정은 기업뿐이다. 기간은 고르게 하지 않는다")
    void newsTakesCompaniesOnly() {
        AgentCatalogResponse.Agent news = service().listAgents().agents().stream()
                .filter(a -> a.agentKey().equals("news")).findFirst().orElseThrow();

        assertThat(news.configSchema().keySet()).containsExactly("corpCodes");
    }

    @Test
    @DisplayName("설정에 적힌 직무만 ready 다")
    void onlyConfiguredRolesAreReady() {
        JobRoleListResponse response = service("backend").listJobRoles();

        assertThat(response.jobRoles())
                .filteredOn(JobRoleListResponse.JobRole::ready)
                .extracting(JobRoleListResponse.JobRole::key)
                .containsExactly("backend");
    }

    @Test
    @DisplayName("지식베이스가 없는 직무는 목록에 남되 topics 가 빈 배열이다")
    void notReadyRoleKeepsItsPlaceButHasNoTopics() {
        JobRoleListResponse response = service("backend").listJobRoles();

        JobRoleListResponse.JobRole frontend = response.jobRoles().stream()
                .filter(r -> r.key().equals("frontend")).findFirst().orElseThrow();
        assertThat(frontend.ready()).isFalse();
        assertThat(frontend.topics()).isEmpty();

        JobRoleListResponse.JobRole backend = response.jobRoles().stream()
                .filter(r -> r.key().equals("backend")).findFirst().orElseThrow();
        assertThat(backend.topics()).isNotEmpty();
    }

    @Test
    @DisplayName("설정이 비어 있으면 모든 직무가 ready=false 다")
    void emptyConfigMeansNothingIsReady() {
        JobRoleListResponse response = service().listJobRoles();

        assertThat(response.jobRoles()).isNotEmpty();
        assertThat(response.jobRoles()).noneMatch(JobRoleListResponse.JobRole::ready);
    }
}

package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.config.AgentCatalogProperties;
import com.ssafy.companyanalysis.agent.domain.AgentType;
import com.ssafy.companyanalysis.agent.domain.RoomAgent;
import com.ssafy.companyanalysis.agent.dto.RoomCreateRequest;
import com.ssafy.companyanalysis.company.domain.Company;
import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;

class RoomAgentValidatorTest {

    private CompanyRepository companyRepository;

    @BeforeEach
    void setUp() {
        companyRepository = Mockito.mock(CompanyRepository.class);
        given(companyRepository.findAllById(any())).willAnswer(invocation -> {
            Iterable<String> codes = invocation.getArgument(0);
            return java.util.stream.StreamSupport.stream(codes.spliterator(), false)
                    .map(RoomAgentValidatorTest::company)
                    .toList();
        });
    }

    private static Company company(String corpCode) {
        Company company = Mockito.mock(Company.class);
        given(company.getCorpCode()).willReturn(corpCode);
        given(company.getCorpName()).willReturn("회사" + corpCode);
        return company;
    }

    private RoomAgentValidator validator(Set<String> readyRoles, Set<String> indexedCorpCodes) {
        return new RoomAgentValidator(companyRepository,
                new AgentCatalogProperties(readyRoles, indexedCorpCodes));
    }

    private static RoomCreateRequest.AgentSpec spec(String key, Map<String, Object> config) {
        return new RoomCreateRequest.AgentSpec(key, config);
    }

    @Test
    @DisplayName("총괄은 사용자가 직접 넣을 수 없다")
    void supervisorCannotBeChosen() {
        assertThatThrownBy(() -> validator(Set.of(), Set.of()).validateAll(List.of(spec("supervisor", Map.of()))))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.AGENT_NOT_SUPPORTED);
    }

    @Test
    @DisplayName("모르는 에이전트 키는 AGENT_NOT_SUPPORTED")
    void unknownAgentKeyIsRejected() {
        assertThatThrownBy(() -> validator(Set.of(), Set.of()).validateAll(List.of(spec("없는에이전트", Map.of()))))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.AGENT_NOT_SUPPORTED);
    }

    @Test
    @DisplayName("같은 에이전트를 두 번 넣으면 INVALID_PARAMETER")
    void duplicateAgentIsRejected() {
        List<RoomCreateRequest.AgentSpec> specs = List.of(
                spec("writing", Map.of()), spec("writing", Map.of()));

        assertThatThrownBy(() -> validator(Set.of(), Set.of()).validateAll(specs))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.INVALID_PARAMETER);
    }

    @Test
    @DisplayName("필수 설정이 비어 있으면 AGENT_CONFIG_REQUIRED")
    void missingRequiredConfigIsRejected() {
        assertThatThrownBy(() -> validator(Set.of(), Set.of())
                .validateAll(List.of(spec("company", Map.of("corpCodes", List.of())))))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.AGENT_CONFIG_REQUIRED);
    }

    @Test
    @DisplayName("모르는 직무는 JOB_ROLE_NOT_SUPPORTED")
    void unknownJobRoleIsRejected() {
        assertThatThrownBy(() -> validator(Set.of(), Set.of())
                .validateAll(List.of(spec("position", Map.of("jobRole", "점성술")))))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.JOB_ROLE_NOT_SUPPORTED);
    }

    @Test
    @DisplayName("인덱싱 목록을 모르면(비어 있으면) 기업 선택을 막지 않는다")
    void emptyIndexAllowlistDoesNotBlock() {
        List<RoomAgent> agents = validator(Set.of(), Set.of())
                .validateAll(List.of(spec("company", Map.of("corpCodes", List.of("00126380")))));

        assertThat(agents).singleElement()
                .satisfies(agent -> assertThat(agent.config()).containsEntry("corpCodes", List.of("00126380")));
    }

    @Test
    @DisplayName("인덱싱 목록이 채워지면 그 밖의 기업은 COMPANY_RAG_NOT_INDEXED")
    void unindexedCompanyIsRejectedOnceAllowlistIsKnown() {
        assertThatThrownBy(() -> validator(Set.of(), Set.of("00126380"))
                .validateAll(List.of(spec("company", Map.of("corpCodes", List.of("00999999"))))))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.COMPANY_RAG_NOT_INDEXED);
    }

    @Test
    @DisplayName("스키마에 없는 키는 저장하지 않고 버린다")
    void unknownConfigKeysAreDropped() {
        Map<String, Object> cleaned = validator(Set.of(), Set.of())
                .validateConfig(AgentType.WRITING, Map.of("아무거나", "값"));

        assertThat(cleaned).isEmpty();
    }

    @Test
    @DisplayName("선택 항목은 없어도 통과하고 있으면 남는다")
    void optionalConfigIsKept() {
        RoomAgentValidator validator = validator(Set.of(), Set.of());

        assertThat(validator.validateConfig(AgentType.NEWS, Map.of("corpCodes", List.of("00126380"))))
                .doesNotContainKey("months");
        assertThat(validator.validateConfig(AgentType.NEWS, Map.of("corpCodes", List.of("00126380"), "months", 3)))
                .containsEntry("months", 3);
    }
}

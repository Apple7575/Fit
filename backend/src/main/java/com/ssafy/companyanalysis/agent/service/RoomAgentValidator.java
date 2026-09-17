package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.config.AgentCatalogProperties;
import com.ssafy.companyanalysis.agent.domain.AgentType;
import com.ssafy.companyanalysis.agent.domain.ConfigField;
import com.ssafy.companyanalysis.agent.domain.RoomAgent;
import com.ssafy.companyanalysis.agent.dto.RoomCreateRequest;
import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 방에 들어가는 에이전트와 설정이 말이 되는지 본다.
 *
 * <p>{@code agents} 가 JSONB 라 DB 가 막아주지 않는다. 막는 자리는 여기 하나뿐이다.
 */
@Component
public class RoomAgentValidator {

    /** 자소서의 지원 직무 칸과 같은 한도. */
    private static final int MAX_JOB_ROLE_LENGTH = 120;

    private final CompanyRepository companyRepository;
    private final AgentCatalogProperties properties;

    public RoomAgentValidator(CompanyRepository companyRepository, AgentCatalogProperties properties) {
        this.companyRepository = companyRepository;
        this.properties = properties;
    }

    /** 사용자가 고른 에이전트 목록을 검증해 저장 형태로 바꾼다. 총괄은 여기서 받지 않는다. */
    public List<RoomAgent> validateAll(List<RoomCreateRequest.AgentSpec> specs) {
        Set<String> seen = new LinkedHashSet<>();
        List<RoomAgent> validated = new ArrayList<>();
        for (RoomCreateRequest.AgentSpec spec : specs) {
            AgentType type = resolveSelectable(spec.agentKey());
            if (!seen.add(type.key())) {
                throw new BusinessException(ErrorCode.INVALID_PARAMETER,
                        "같은 에이전트를 두 번 넣을 수 없습니다: " + type.key());
            }
            validated.add(new RoomAgent(type.key(), validateConfig(type, spec.config())));
        }
        return validated;
    }

    /** 사용자가 고를 수 있는 에이전트인지 본다. 총괄은 서버가 붙이는 것이라 직접 넣을 수 없다. */
    public AgentType resolveSelectable(String agentKey) {
        AgentType type = AgentType.from(agentKey)
                .orElseThrow(() -> new BusinessException(ErrorCode.AGENT_NOT_SUPPORTED,
                        "지원하지 않는 에이전트입니다: " + agentKey));
        if (!type.selectable()) {
            throw new BusinessException(ErrorCode.AGENT_NOT_SUPPORTED,
                    "직접 넣을 수 없는 에이전트입니다: " + agentKey);
        }
        return type;
    }

    /**
     * 설정 값이 말이 되는지 본다. 통과하면 스키마에 있는 키만 남긴 맵을 준다.
     *
     * <p>덜 채운 설정도 저장한다 — 고르다 만 상태를 그대로 두는 편이 낫다. 값이 들어 있으면
     * 그 값이 올바른지는 여기서 본다(없는 기업, 모르는 직무).
     */
    public Map<String, Object> validateConfig(AgentType type, Map<String, Object> config) {
        Map<String, Object> source = config == null ? Map.of() : config;
        Map<String, Object> cleaned = new java.util.LinkedHashMap<>();

        for (Map.Entry<String, ConfigField> entry : type.configSchema().entrySet()) {
            String name = entry.getKey();
            Object value = source.get(name);
            if (isEmpty(value)) {
                // 필수 항목이 비어도 여기서 막지 않는다. 방은 자소서를 고르면 자동으로 만들어지고,
                // 설정은 그 방에 들어가서 채우기 때문이다. 다 찼는지는 실제로 돌릴 때 본다
                // (AgentType#isConfigured).
                continue;
            }
            cleaned.put(name, normalize(name, value));
        }
        return cleaned;
    }

    private Object normalize(String name, Object value) {
        return switch (name) {
            case "corpCodes" -> validateCorpCodes(value);
            case "jobRole" -> validateJobRole(value);
            default -> value;
        };
    }

    private List<String> validateCorpCodes(Object value) {
        if (!(value instanceof Collection<?> raw)) {
            throw new BusinessException(ErrorCode.INVALID_PARAMETER, "corpCodes 는 배열이어야 합니다.");
        }
        List<String> corpCodes = raw.stream().map(String::valueOf).distinct().toList();

        Set<String> existing = new LinkedHashSet<>(
                companyRepository.findAllById(corpCodes).stream()
                        .map(company -> company.getCorpCode())
                        .toList());
        for (String corpCode : corpCodes) {
            if (!existing.contains(corpCode)) {
                throw new BusinessException(ErrorCode.COMPANY_NOT_FOUND, "없는 기업입니다: " + corpCode);
            }
            if (!properties.isRagIndexed(corpCode)) {
                throw new BusinessException(ErrorCode.COMPANY_RAG_NOT_INDEXED,
                        "분석 자료가 아직 준비되지 않은 기업입니다: " + corpCode);
            }
        }
        return corpCodes;
    }

    /**
     * 직무는 공고에 쓰인 문구가 그대로 들어온다. 고정 목록으로 거르지 않는다 —
     * 자소서에서 고른 "서버 개발(Java/Spring)" 같은 값을 받아야 한다.
     */
    private String validateJobRole(Object value) {
        String jobRole = String.valueOf(value).trim();
        if (jobRole.length() > MAX_JOB_ROLE_LENGTH) {
            throw new BusinessException(ErrorCode.INVALID_PARAMETER,
                    "직무는 " + MAX_JOB_ROLE_LENGTH + "자 이하여야 합니다.");
        }
        return jobRole;
    }

    private static boolean isEmpty(Object value) {
        if (value == null) {
            return true;
        }
        if (value instanceof String text) {
            return text.isBlank();
        }
        if (value instanceof Collection<?> collection) {
            return collection.isEmpty();
        }
        return false;
    }
}

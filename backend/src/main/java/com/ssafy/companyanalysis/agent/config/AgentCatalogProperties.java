package com.ssafy.companyanalysis.agent.config;

import com.ssafy.companyanalysis.agent.domain.JobRole;
import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.Set;

/**
 * 아직 코드로 알 수 없는 두 가지 준비 상태를 설정으로 받는다. 둘 다 적재가 하는 일이라
 * 코드 배포와 시점이 다르다.
 *
 * @param readyJobRoles      직무 지식베이스가 적재된 직무({@link JobRole#key()}). 비면 전부 ready=false
 * @param ragIndexedCorpCodes Vector DB 가 만들어진 기업의 corpCode.
 *                            <b>비어 있으면 "아직 알 수 없음" 으로 보고 검사하지 않는다</b> —
 *                            인덱싱 파이프라인(S15P21A504-132)이 오기 전에 모든 기업 선택을
 *                            막아 버리면 기능 자체를 쓸 수 없기 때문이다. 값이 차면 그때부터 강제한다
 */
@ConfigurationProperties(prefix = "app.agent")
public record AgentCatalogProperties(Set<String> readyJobRoles, Set<String> ragIndexedCorpCodes) {

    public AgentCatalogProperties {
        readyJobRoles = readyJobRoles == null ? Set.of() : Set.copyOf(readyJobRoles);
        ragIndexedCorpCodes = ragIndexedCorpCodes == null ? Set.of() : Set.copyOf(ragIndexedCorpCodes);
    }

    public boolean isReady(JobRole role) {
        return readyJobRoles.contains(role.key());
    }

    /** 인덱싱 목록을 모르면(비어 있으면) 막지 않는다. */
    public boolean isRagIndexed(String corpCode) {
        return ragIndexedCorpCodes.isEmpty() || ragIndexedCorpCodes.contains(corpCode);
    }

    public boolean ragIndexKnown() {
        return !ragIndexedCorpCodes.isEmpty();
    }
}

package com.ssafy.companyanalysis.agent.config;

import com.ssafy.companyanalysis.agent.domain.JobRole;
import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.Set;

/**
 * 코드가 알 수 없는 두 가지를 설정으로 받는다. 성격이 서로 다르니 섞어 읽지 않는다 —
 * 직무는 <b>우리가 여닫는 스위치</b>이고, 기업은 <b>적재가 끝났는지</b>다.
 *
 * @param readyJobRoles      쓸 수 있게 열어 둔 직무({@link JobRole#key()}). 비면 전부 ready=false.
 *                           <b>직무를 위한 적재는 없다</b> — 포지션 담당은 저장소를 뒤지지 않고
 *                           직무명과 관점 힌트를 프롬프트에 받아 모델 지식으로 답한다.
 *                           그래서 이 값은 답변 품질이 아니라 고를 수 있는지만 가른다
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

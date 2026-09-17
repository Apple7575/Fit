package com.ssafy.companyanalysis.agent.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.Set;

/**
 * 코드가 알 수 없는 것을 설정으로 받는다.
 *
 * @param ragIndexedCorpCodes Vector DB 가 만들어진 기업의 corpCode.
 *                            <b>비어 있으면 "아직 알 수 없음" 으로 보고 검사하지 않는다</b> —
 *                            인덱싱 파이프라인(S15P21A504-132)이 오기 전에 모든 기업 선택을
 *                            막아 버리면 기능 자체를 쓸 수 없기 때문이다. 값이 차면 그때부터 강제한다
 */
@ConfigurationProperties(prefix = "app.agent")
public record AgentCatalogProperties(Set<String> ragIndexedCorpCodes) {

    public AgentCatalogProperties {
        ragIndexedCorpCodes = ragIndexedCorpCodes == null ? Set.of() : Set.copyOf(ragIndexedCorpCodes);
    }

    /** 인덱싱 목록을 모르면(비어 있으면) 막지 않는다. */
    public boolean isRagIndexed(String corpCode) {
        return ragIndexedCorpCodes.isEmpty() || ragIndexedCorpCodes.contains(corpCode);
    }

    public boolean ragIndexKnown() {
        return !ragIndexedCorpCodes.isEmpty();
    }
}

package com.ssafy.companyanalysis.agent.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.ConstructorBinding;

import java.util.Locale;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * 코드가 알 수 없는 것을 설정으로 받는다.
 *
 * @param ragIndexedCorpCodes Vector DB 가 만들어진 기업의 corpCode.
 *                            <b>비어 있으면 "아직 알 수 없음" 으로 보고 검사하지 않는다</b> —
 *                            인덱싱 파이프라인(S15P21A504-132)이 오기 전에 모든 기업 선택을
 *                            막아 버리면 기능 자체를 쓸 수 없기 때문이다. 값이 차면 그때부터 강제한다
 * @param hiddenAgents        화면에서 감출 담당의 agentKey. <b>구현이 덜 된 담당을 QA 동안 안 보이게
 *                            해 두는 스위치다</b> — 코드를 지웠다 되살리는 대신 환경별로 끄고 켠다.
 *                            기능을 떼는 것이 아니라 가리는 것이라, 서버 API 도 AI 워커도 그대로 돈다.
 *                            방에 저장된 담당 목록도 건드리지 않아 다시 켜면 그대로 돌아온다
 */
@ConfigurationProperties(prefix = "app.agent")
public record AgentCatalogProperties(Set<String> ragIndexedCorpCodes, Set<String> hiddenAgents) {

    // 생성자가 둘이라 Spring 이 어느 쪽으로 설정을 바인딩할지 알 수 없다. 표시가 없으면 뜰 때 터진다.
    @ConstructorBinding
    public AgentCatalogProperties {
        ragIndexedCorpCodes = ragIndexedCorpCodes == null ? Set.of() : Set.copyOf(ragIndexedCorpCodes);
        // 설정 파일에 "News" 나 " news " 로 적혀도 통하게 한다. agentKey 는 전부 소문자다.
        hiddenAgents = hiddenAgents == null
                ? Set.of()
                : hiddenAgents.stream()
                        .filter(key -> key != null && !key.isBlank())
                        .map(key -> key.trim().toLowerCase(Locale.ROOT))
                        .collect(Collectors.toUnmodifiableSet());
    }

    /** 감출 담당을 안 적은 환경(기본값)에서 쓰던 생성자. 전부 보이는 상태다. */
    public AgentCatalogProperties(Set<String> ragIndexedCorpCodes) {
        this(ragIndexedCorpCodes, Set.of());
    }

    /** 인덱싱 목록을 모르면(비어 있으면) 막지 않는다. */
    public boolean isRagIndexed(String corpCode) {
        return ragIndexedCorpCodes.isEmpty() || ragIndexedCorpCodes.contains(corpCode);
    }

    public boolean ragIndexKnown() {
        return !ragIndexedCorpCodes.isEmpty();
    }

    /** 지금 화면에 내보이는 담당인지. 감춘 담당은 목록에도 말풍선에도 안 나온다. */
    public boolean isAgentVisible(String agentKey) {
        return agentKey != null && !hiddenAgents.contains(agentKey.toLowerCase(Locale.ROOT));
    }
}

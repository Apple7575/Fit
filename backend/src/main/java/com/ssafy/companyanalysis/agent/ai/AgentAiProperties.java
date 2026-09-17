package com.ssafy.companyanalysis.agent.ai;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

/**
 * 담당 에이전트를 맡은 AI 서버(FastAPI) 접속 정보.
 *
 * <p>주소가 비면 에이전트를 부르지 않고 자기 자리에서 실패한다. 주소 없이 호출하면 연결 오류
 * 문구가 그대로 화면에 뜬다.
 *
 * <p>시간 제한을 둘로 나눈 이유는 한 번에 도는 분량이 다르기 때문이다. 공고 등록 같은 단발
 * 호출은 {@code timeout} 을 쓰고, 담당 여럿을 돌려 종합하는 총괄은 {@code supervisorTimeout}
 * 을 쓴다 — 총괄 명세가 정해 둔 값이 120초다.
 */
@ConfigurationProperties(prefix = "app.ai.agent")
public record AgentAiProperties(String baseUrl, Duration timeout, Duration supervisorTimeout) {

    public AgentAiProperties {
        timeout = timeout == null ? Duration.ofSeconds(150) : timeout;
        supervisorTimeout = supervisorTimeout == null ? Duration.ofSeconds(120) : supervisorTimeout;
    }

    public boolean hasBaseUrl() {
        return baseUrl != null && !baseUrl.isBlank();
    }
}

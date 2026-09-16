package com.ssafy.companyanalysis.agent.ai;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

/**
 * 포지션·글쓰기 에이전트를 맡은 AI 서버(FastAPI) 접속 정보.
 *
 * <p>주소가 비면 두 에이전트는 부르지 않고 자기 자리에서 실패한다. 주소 없이 호출하면
 * 연결 오류 문구가 그대로 화면에 뜬다.
 *
 * <p>기본 시간 제한이 긴 이유는 Qwen 응답이 느리기 때문이다(모의 면접 실측 ~58초).
 */
@ConfigurationProperties(prefix = "app.ai.agent")
public record AgentAiProperties(String baseUrl, Duration timeout) {

    public AgentAiProperties {
        timeout = timeout == null ? Duration.ofSeconds(150) : timeout;
    }

    public boolean hasBaseUrl() {
        return baseUrl != null && !baseUrl.isBlank();
    }
}

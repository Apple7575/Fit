package com.ssafy.companyanalysis.interview.ai;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

/** vLLM(OpenAI 호환) 접속 설정. key 는 환경변수(LLM_KEY)로만 넣고 클라이언트에 노출하지 않는다. */
@ConfigurationProperties(prefix = "app.ai.vllm")
public record VllmProperties(String baseUrl, String key, String model, Duration timeout) {

    private static final String DEFAULT_MODEL = "main";
    private static final Duration DEFAULT_TIMEOUT = Duration.ofSeconds(60);

    public VllmProperties {
        baseUrl = (baseUrl == null || baseUrl.isBlank()) ? "" : baseUrl.replaceAll("/+$", "");
        model = (model == null || model.isBlank()) ? DEFAULT_MODEL : model;
        timeout = timeout == null ? DEFAULT_TIMEOUT : timeout;
    }

    public boolean hasKey() {
        return key != null && !key.isBlank();
    }
}

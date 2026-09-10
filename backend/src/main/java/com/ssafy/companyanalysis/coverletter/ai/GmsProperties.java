package com.ssafy.companyanalysis.coverletter.ai;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

/** GMS 접속 설정. key 는 환경변수(GMS_KEY)로만 넣고 클라이언트에 노출하지 않는다. */
@ConfigurationProperties(prefix = "app.ai.gms")
public record GmsProperties(String baseUrl, String key, String model, Duration timeout) {

    private static final String DEFAULT_BASE_URL = "https://gms.ssafy.io/gmsapi";
    private static final String DEFAULT_MODEL = "gemini-2.5-flash";
    private static final Duration DEFAULT_TIMEOUT = Duration.ofSeconds(30);

    public GmsProperties {
        baseUrl = (baseUrl == null || baseUrl.isBlank())
                ? DEFAULT_BASE_URL
                : baseUrl.replaceAll("/+$", "");
        model = (model == null || model.isBlank()) ? DEFAULT_MODEL : model;
        timeout = timeout == null ? DEFAULT_TIMEOUT : timeout;
    }

    public boolean hasKey() {
        return key != null && !key.isBlank();
    }
}

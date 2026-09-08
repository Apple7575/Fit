package com.ssafy.companyanalysis.global.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.List;

/**
 * {@code /api/**} 의 CORS 설정.
 *
 * <p>세션 쿠키를 교차 오리진(로컬 FE:5173)에서 실어 보내야 하므로 {@code allowCredentials} 를 켠다.
 * 자격증명 요청은 와일드카드 Origin 을 허용하지 않으므로 아래 허용 Origin 은 항상 명시값이어야 한다.
 * 배포는 nginx 로 같은 오리진이라 허용 Origin 이 비어 매핑 자체가 등록되지 않는다.
 *
 * <p>허용 Origin 이 하나도 없으면 매핑 자체를 등록하지 않는다. 이 상태에서 preflight 는
 * 403 으로 거부된다.
 */
@Configuration
@EnableConfigurationProperties(CorsProperties.class)
public class WebCorsConfig implements WebMvcConfigurer {

    private static final Logger log = LoggerFactory.getLogger(WebCorsConfig.class);

    private static final String[] ALLOWED_METHODS = {"GET", "HEAD", "OPTIONS", "POST"};

    /** X-XSRF-TOKEN 은 변경 요청의 CSRF 토큰을 실어 보내는 헤더다. */
    private static final String[] ALLOWED_HEADERS = {"Accept", "Content-Type", "X-XSRF-TOKEN"};

    private final CorsProperties corsProperties;

    public WebCorsConfig(CorsProperties corsProperties) {
        this.corsProperties = corsProperties;
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        List<String> allowedOrigins = corsProperties.allowedOrigins();
        if (allowedOrigins.isEmpty()) {
            log.info("app.cors.allowed-origins 가 비어 있어 CORS 를 켜지 않는다. 같은 오리진 요청만 받는다.");
            return;
        }

        log.info("CORS 허용 Origin: {}", allowedOrigins);
        registry.addMapping("/api/**")
                .allowedOrigins(allowedOrigins.toArray(String[]::new))
                .allowedMethods(ALLOWED_METHODS)
                .allowedHeaders(ALLOWED_HEADERS)
                .allowCredentials(true)
                .maxAge(corsProperties.maxAge().toSeconds());
    }
}

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
 * <p>MVP API 는 전부 인증 없는 조회다. 쿠키나 인증 헤더를 실어 보낼 일이 없어
 * {@code allowCredentials} 는 끈 채로 둔다. 이걸 켜면 Origin 별 응답 캐시 오염과 CSRF 를
 * 같이 떠안게 되므로, 인증이 생기는 시점에 별도로 검토한다.
 *
 * <p>허용 Origin 이 하나도 없으면 매핑 자체를 등록하지 않는다. 이 상태에서 preflight 는
 * 403 으로 거부된다.
 */
@Configuration
@EnableConfigurationProperties(CorsProperties.class)
public class WebCorsConfig implements WebMvcConfigurer {

    private static final Logger log = LoggerFactory.getLogger(WebCorsConfig.class);

    /** 현재 API 는 조회 전용이다. 쓰기 메서드가 생기면 여기에 명시적으로 추가한다. */
    private static final String[] ALLOWED_METHODS = {"GET", "HEAD", "OPTIONS"};

    /** FE 는 {@code Accept: application/json} 만 붙인다. 그 외 헤더는 필요해질 때 연다. */
    private static final String[] ALLOWED_HEADERS = {"Accept", "Content-Type"};

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
                .allowCredentials(false)
                .maxAge(corsProperties.maxAge().toSeconds());
    }
}

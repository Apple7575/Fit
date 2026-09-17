package com.ssafy.companyanalysis.global.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;
import java.util.List;

/**
 * 교차 출처 요청 허용 정책. {@code app.cors.*} 로 주입한다.
 *
 * <p>허용 Origin 을 코드가 아니라 설정으로 두는 이유는 배포 환경마다 FE 오리진이 다르기 때문이다.
 * 기본값은 빈 목록이고, 이때 CORS 는 아예 켜지지 않는다. 컨테이너 배포는 Nginx 가 FE·BE 를
 * 같은 오리진으로 묶으므로 교차 출처 자체가 생기지 않는 것이 정상이다.
 *
 * @param allowedOrigins 허용할 Origin 목록. 스킴·호스트·포트까지 정확히 일치해야 한다
 * @param maxAge         preflight 응답을 브라우저가 캐시하는 시간
 */
@ConfigurationProperties(prefix = "app.cors")
public record CorsProperties(List<String> allowedOrigins, Duration maxAge) {

    private static final Duration DEFAULT_MAX_AGE = Duration.ofHours(1);

    public CorsProperties {
        // `app.cors.allowed-origins=` 처럼 키만 두고 값을 비우면 빈 문자열 항목이 섞여 들어온다.
        // 그대로 두면 Origin "" 을 허용 목록에 올리게 되므로 여기서 걸러 낸다.
        allowedOrigins = allowedOrigins == null
                ? List.of()
                : allowedOrigins.stream()
                        .map(String::trim)
                        .filter(origin -> !origin.isEmpty())
                        .toList();
        maxAge = maxAge == null ? DEFAULT_MAX_AGE : maxAge;
    }
}

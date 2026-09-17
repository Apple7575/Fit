package com.ssafy.companyanalysis.global.config;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 설정값이 어떻게 들어와도 허용 목록이 망가지지 않아야 한다.
 *
 * <p>Origin 목록은 환경변수로 주입되는 값이라 공백이나 빈 항목이 섞이기 쉽다.
 * 그대로 통과시키면 Origin "" 을 허용해 버리거나 공백 때문에 매칭이 조용히 실패한다.
 */
class CorsPropertiesTest {

    @Test
    @DisplayName("설정이 아예 없으면 허용 Origin 은 빈 목록이고 max-age 는 1시간이다")
    void defaultsAreSafe() {
        CorsProperties properties = new CorsProperties(null, null);

        assertThat(properties.allowedOrigins()).isEmpty();
        assertThat(properties.maxAge()).isEqualTo(Duration.ofHours(1));
    }

    @Test
    @DisplayName("빈 문자열 항목은 허용 목록에서 걸러진다")
    void blankOriginsAreDropped() {
        // `APP_CORS_ALLOWED_ORIGINS=` 로 값을 비우면 [""] 가 들어온다
        CorsProperties properties = new CorsProperties(Arrays.asList("", "   "), null);

        assertThat(properties.allowedOrigins()).isEmpty();
    }

    @Test
    @DisplayName("콤마 뒤 공백이 붙은 Origin 도 정확히 매칭되도록 다듬는다")
    void originsAreTrimmed() {
        CorsProperties properties =
                new CorsProperties(List.of(" http://localhost:5173", "http://127.0.0.1:5173 "), null);

        assertThat(properties.allowedOrigins())
                .containsExactly("http://localhost:5173", "http://127.0.0.1:5173");
    }
}

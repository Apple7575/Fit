package com.ssafy.companyanalysis.global.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Clock;
import java.time.ZoneId;

@Configuration
public class TimeConfig {

    /**
     * 기준연도 계산에 쓰는 시계.
     *
     * <p>서울로 못박는다. DART 제출 기한이 한국 시간 기준이라 서버가 UTC 로 돌면
     * 연말연시와 분기 경계에서 하루가 밀리고, 그 하루가 기준연도를 한 해 바꾼다.
     *
     * <p>주입받는 이유는 테스트다. "3월일 때"와 "4월일 때"를 확인하려면 시계를
     * 갈아끼울 수 있어야 한다.
     */
    @Bean
    public Clock clock() {
        return Clock.system(ZoneId.of("Asia/Seoul"));
    }
}

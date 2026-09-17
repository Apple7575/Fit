package com.ssafy.companyanalysis.agent.ai;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.time.Duration;

@Configuration
@EnableConfigurationProperties(AgentAiProperties.class)
public class AgentAiConfig {

    @Bean
    public RestClient agentAiRestClient(AgentAiProperties properties) {
        return build(properties, properties.timeout());
    }

    /** 총괄·뉴스처럼 담당을 여럿 돌리는 호출. 명세가 정한 120초를 기본으로 쓴다. */
    @Bean
    public RestClient supervisorAiRestClient(AgentAiProperties properties) {
        return build(properties, properties.supervisorTimeout());
    }

    private static RestClient build(AgentAiProperties properties, Duration timeout) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        int timeoutMs = (int) timeout.toMillis();
        factory.setConnectTimeout(timeoutMs);
        factory.setReadTimeout(timeoutMs);
        return RestClient.builder()
                .baseUrl(properties.hasBaseUrl() ? properties.baseUrl() : "http://ai-service.invalid")
                .requestFactory(factory)
                .build();
    }
}

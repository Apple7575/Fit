package com.ssafy.companyanalysis.agent.ai;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

@Configuration
@EnableConfigurationProperties(AgentAiProperties.class)
public class AgentAiConfig {

    @Bean
    public RestClient agentAiRestClient(AgentAiProperties properties) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        int timeoutMs = (int) properties.timeout().toMillis();
        factory.setConnectTimeout(timeoutMs);
        factory.setReadTimeout(timeoutMs);
        return RestClient.builder()
                .baseUrl(properties.hasBaseUrl() ? properties.baseUrl() : "http://ai-service.invalid")
                .requestFactory(factory)
                .build();
    }
}

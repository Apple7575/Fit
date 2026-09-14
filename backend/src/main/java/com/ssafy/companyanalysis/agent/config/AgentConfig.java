package com.ssafy.companyanalysis.agent.config;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/** 자소서 멀티에이전트 설정 바인딩. */
@Configuration
@EnableConfigurationProperties(AgentCatalogProperties.class)
public class AgentConfig {
}

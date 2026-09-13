package com.ssafy.companyanalysis.agent.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

/**
 * 에이전트를 병렬로 돌리는 풀.
 *
 * <p>공용 @Async 풀을 쓰지 않는다. 에이전트 호출은 LLM 대기라 수십 초씩 스레드를 잡는데,
 * 메일 발송 같은 다른 비동기 작업이 같은 풀에 있으면 함께 막힌다.
 */
@Configuration
public class AgentExecutorConfig {

    @Bean(name = "agentTaskExecutor")
    public ThreadPoolTaskExecutor agentTaskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(4);
        executor.setMaxPoolSize(8);
        // 방마다 한 턴만 돌고 한 턴은 에이전트 다섯이므로 큐가 길 필요가 없다.
        executor.setQueueCapacity(32);
        executor.setThreadNamePrefix("agent-");
        executor.setWaitForTasksToCompleteOnShutdown(true);
        executor.setAwaitTerminationSeconds(30);
        return executor;
    }
}

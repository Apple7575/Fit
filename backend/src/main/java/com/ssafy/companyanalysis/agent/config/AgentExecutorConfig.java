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

    /**
     * 자동 검토가 방을 하나씩 도는 자리.
     *
     * <p>스레드 하나뿐이다. 자동 검토는 방 여러 개를 연달아 도는데, 한 방을 이끄는 스레드는
     * 그 방 에이전트가 끝날 때까지 기다린다. 이끄는 스레드가 여럿이면 위 풀의 자리를 모두
     * 차지해 에이전트가 시작조차 못 하고, 서로를 기다리며 멈춘다.
     *
     * <p>이끄는 일을 위 풀과 나눠 둔 것도 같은 이유다. 같은 풀에 섞으면 자리 다툼이 그대로다.
     */
    @Bean(name = "autoReviewExecutor")
    public ThreadPoolTaskExecutor autoReviewExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(1);
        executor.setMaxPoolSize(1);
        // 자소서 하나가 방 여섯을 깔고, 그 사이 다른 자소서를 열 수도 있다.
        executor.setQueueCapacity(64);
        executor.setThreadNamePrefix("auto-review-");
        executor.setWaitForTasksToCompleteOnShutdown(false);
        return executor;
    }
}

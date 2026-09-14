package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 발화 한 번에 LLM 을 다섯 번 부르므로 비용 방어가 필요하다.
 *
 * <p>{@code FeedbackRateLimiter} 를 재사용하지 않는다. 그쪽은 게스트(IP)와 로그인을 나누고
 * FEEDBACK_RATE_LIMITED 를 던지도록 박혀 있는데, 검토 방은 로그인 전용이고 명세가 다른
 * 에러코드를 쓴다.
 *
 * <p>인메모리라 인스턴스가 늘면 공유 저장소로 옮겨야 한다 — 기존 레이트리미터와 같은 한계다.
 */
@Component
public class AnalysisRateLimiter {

    private final int userLimit;
    private final long windowMillis;
    private final ConcurrentHashMap<Long, Window> windows = new ConcurrentHashMap<>();

    public AnalysisRateLimiter(
            @Value("${app.agent.rate-limit.user-limit:20}") int userLimit,
            @Value("${app.agent.rate-limit.window:1h}") Duration window) {
        this.userLimit = userLimit;
        this.windowMillis = window.toMillis();
    }

    public void check(Long userId) {
        long now = System.currentTimeMillis();
        Window updated = windows.compute(userId, (key, existing) ->
                (existing == null || now - existing.start() >= windowMillis)
                        ? new Window(now, 1)
                        : new Window(existing.start(), existing.count() + 1));
        if (updated.count() > userLimit) {
            throw new BusinessException(ErrorCode.ANALYSIS_RATE_LIMITED);
        }
    }

    private record Window(long start, int count) {
    }
}

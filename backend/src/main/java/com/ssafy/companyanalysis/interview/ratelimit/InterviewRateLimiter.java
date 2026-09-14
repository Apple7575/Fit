package com.ssafy.companyanalysis.interview.ratelimit;

import com.ssafy.companyanalysis.auth.service.UserPrincipal;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 면접 LLM 호출(질문 생성·분석·꼬리질문) 남용·비용 방어. 로그인 전용이라 userId 기준만 센다.
 * 단일 인스턴스 인메모리 방식이라, 다중 인스턴스로 확장하면 공유 저장소(Redis 등)로 옮겨야 한다.
 */
@Component
public class InterviewRateLimiter {

    private final int userLimit;
    private final long windowMillis;
    private final ConcurrentHashMap<Long, Window> windows = new ConcurrentHashMap<>();

    public InterviewRateLimiter(
            @Value("${app.interview.rate-limit.user-limit:40}") int userLimit,
            @Value("${app.interview.rate-limit.window:1h}") Duration window) {
        this.userLimit = userLimit;
        this.windowMillis = window.toMillis();
    }

    public void check(UserPrincipal principal) {
        long now = System.currentTimeMillis();
        Window updated = windows.compute(principal.getId(), (k, existing) ->
                (existing == null || now - existing.start() >= windowMillis)
                        ? new Window(now, 1)
                        : new Window(existing.start(), existing.count() + 1));
        if (updated.count() > userLimit) {
            throw new BusinessException(ErrorCode.FEEDBACK_RATE_LIMITED);
        }
    }

    @Scheduled(fixedDelay = 3_600_000L)
    void purgeExpired() {
        long now = System.currentTimeMillis();
        windows.entrySet().removeIf(entry -> now - entry.getValue().start() >= windowMillis);
    }

    private record Window(long start, int count) {
    }
}

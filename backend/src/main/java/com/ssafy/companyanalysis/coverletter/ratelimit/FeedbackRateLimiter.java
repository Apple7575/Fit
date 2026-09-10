package com.ssafy.companyanalysis.coverletter.ratelimit;

import com.ssafy.companyanalysis.auth.service.UserPrincipal;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 문항 피드백 API 남용·비용 방어. 고정 창(window) 안에서 게스트는 IP, 로그인은 userId 기준으로 횟수를 센다.
 * 단일 인스턴스 인메모리 방식이라, 다중 인스턴스로 확장하면 공유 저장소(Redis 등)로 옮겨야 한다.
 */
@Component
public class FeedbackRateLimiter {

    private final int guestLimit;
    private final int userLimit;
    private final long windowMillis;
    private final ConcurrentHashMap<String, Window> windows = new ConcurrentHashMap<>();

    public FeedbackRateLimiter(
            @Value("${app.feedback.rate-limit.guest-limit:10}") int guestLimit,
            @Value("${app.feedback.rate-limit.user-limit:60}") int userLimit,
            @Value("${app.feedback.rate-limit.window:1h}") Duration window) {
        this.guestLimit = guestLimit;
        this.userLimit = userLimit;
        this.windowMillis = window.toMillis();
    }

    public void check(UserPrincipal principal, HttpServletRequest request) {
        String key = principal != null ? "user:" + principal.getId() : "ip:" + clientIp(request);
        int limit = principal != null ? userLimit : guestLimit;
        long now = System.currentTimeMillis();
        Window updated = windows.compute(key, (k, existing) ->
                (existing == null || now - existing.start() >= windowMillis)
                        ? new Window(now, 1)
                        : new Window(existing.start(), existing.count() + 1));
        if (updated.count() > limit) {
            throw new BusinessException(ErrorCode.FEEDBACK_RATE_LIMITED);
        }
    }

    @Scheduled(fixedDelay = 3_600_000L)
    void purgeExpired() {
        long now = System.currentTimeMillis();
        windows.entrySet().removeIf(entry -> now - entry.getValue().start() >= windowMillis);
    }

    // nginx 가 붙여 주는 원 IP. 신뢰 프록시 뒤가 아니면 위조 가능하다는 한계가 있다.
    private String clientIp(HttpServletRequest request) {
        String forwarded = request.getHeader("X-Forwarded-For");
        if (forwarded != null && !forwarded.isBlank()) {
            return forwarded.split(",")[0].trim();
        }
        return request.getRemoteAddr();
    }

    private record Window(long start, int count) {
    }
}

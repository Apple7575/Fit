package com.ssafy.companyanalysis.jobposting.cache;

import com.ssafy.companyanalysis.agent.ai.JobSourceClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 공고 확인 때 긁어 둔 본문을 등록까지 잠시 들고 있는다.
 *
 * <p>확인과 등록은 사용자가 회사·직무를 보는 사이 몇 분 차이로 이어진다. 그 사이에 본문을
 * 버리면 등록할 때 같은 공고를 한 번 더 긁어야 한다(S15P21A504-140).
 *
 * <p>잃어도 되는 값이라 메모리에 둔다. 서버를 다시 띄우거나 보관 시간이 지나면 사라지고,
 * 그때는 등록 쪽이 주소로 다시 읽는다. 저장소로 쓰려는 것이 아니다.
 *
 * <p>공고 확인은 로그인 없이도 부를 수 있어 본문이 쌓일 수 있다. 개수 상한을 두고, 넘치면
 * 보관하지 않는다 — 못 담아도 등록은 주소로 되므로 기능이 막히지는 않는다.
 *
 * <p>{@link com.ssafy.companyanalysis.jobposting.ratelimit.JobPostingRateLimiter} 와 같은
 * 한계를 갖는다. 인스턴스를 여럿 띄우면 서로의 보관분을 보지 못한다.
 */
@Component
public class JobPostingSourceCache {

    private final Duration ttl;
    private final int maxEntries;
    private final ConcurrentHashMap<String, Entry> entries = new ConcurrentHashMap<>();

    public JobPostingSourceCache(
            @Value("${app.job-posting.source-cache.ttl:30m}") Duration ttl,
            @Value("${app.job-posting.source-cache.max-entries:200}") int maxEntries) {
        this.ttl = ttl;
        this.maxEntries = maxEntries;
    }

    /** @return 등록할 때 돌려받을 보관 키. 담지 못했으면 null */
    public String put(JobSourceClient.JobSource source) {
        if (entries.size() >= maxEntries) {
            purgeExpired();
        }
        if (entries.size() >= maxEntries) {
            return null;
        }
        String key = UUID.randomUUID().toString();
        entries.put(key, new Entry(System.currentTimeMillis(), source));
        return key;
    }

    /** 꺼내도 지우지 않는다. 등록이 한 번 실패해도 사용자가 다시 누를 수 있어야 한다. */
    public Optional<JobSourceClient.JobSource> find(String key) {
        if (key == null || key.isBlank()) {
            return Optional.empty();
        }
        Entry entry = entries.get(key);
        if (entry == null || isExpired(entry, System.currentTimeMillis())) {
            return Optional.empty();
        }
        return Optional.of(entry.source());
    }

    @Scheduled(fixedDelay = 600_000L)
    void purgeExpired() {
        long now = System.currentTimeMillis();
        entries.entrySet().removeIf(entry -> isExpired(entry.getValue(), now));
    }

    private boolean isExpired(Entry entry, long now) {
        return now - entry.storedAt() >= ttl.toMillis();
    }

    private record Entry(long storedAt, JobSourceClient.JobSource source) {
    }
}

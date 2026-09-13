package com.ssafy.companyanalysis.agent.domain;

import java.util.List;

/**
 * 포지션 담당 에이전트가 다루는 직무.
 *
 * <p>{@code topics} 는 그 직무의 지식베이스가 덮는 범위다. 지식베이스가 아직 없는 직무는
 * 목록에 남되 {@code ready = false} 로 나가며 topics 를 내보내지 않는다 —
 * 준비 여부는 이 enum 이 아니라 설정(app.agent.ready-job-roles)이 정한다.
 */
public enum JobRole {

    BACKEND("backend", "백엔드", List.of("동시성", "분산 락", "메시지 큐", "트랜잭션", "캐시")),
    FRONTEND("frontend", "프론트엔드", List.of("렌더링 최적화", "상태 관리", "번들 크기", "접근성")),
    DATA("data", "데이터", List.of("수집 파이프라인", "데이터 모델링", "배치 · 스트리밍")),
    INFRA("infra", "인프라", List.of("컨테이너", "CI/CD", "모니터링", "가용성"));

    private final String key;
    private final String displayName;
    private final List<String> topics;

    JobRole(String key, String displayName, List<String> topics) {
        this.key = key;
        this.displayName = displayName;
        this.topics = topics;
    }

    public static java.util.Optional<JobRole> from(String key) {
        return java.util.Arrays.stream(values()).filter(role -> role.key.equals(key)).findFirst();
    }

    public String key() {
        return key;
    }

    public String displayName() {
        return displayName;
    }

    public List<String> topics() {
        return topics;
    }
}

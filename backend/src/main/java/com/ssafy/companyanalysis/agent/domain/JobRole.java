package com.ssafy.companyanalysis.agent.domain;

import java.util.List;

/**
 * 포지션 담당 에이전트가 다루는 직무.
 *
 * <p><b>직무를 위한 저장소나 검색은 없다.</b> {@code topics} 는 어딘가에 적재된 자료의
 * 목차가 아니라, 프롬프트에 그대로 넣어 모델이 어느 관점에서 볼지 잡아 주는 힌트다
 * (예: "백엔드 (동시성, 분산 락, …)"). 답은 모델이 원래 아는 것에서 나온다.
 *
 * <p>{@code ready} 는 이 enum 이 아니라 설정(app.agent.ready-job-roles)이 정하며,
 * 무엇이 준비됐는지가 아니라 <b>그 직무를 열어 둘지</b>를 뜻한다. 닫힌 직무는 목록에
 * 남되 고를 수 없고 topics 도 내보내지 않는다. 배포 없이 직무를 여닫으려고 둔 스위치다.
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

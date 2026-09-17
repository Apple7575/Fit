package com.ssafy.companyanalysis.agent.ai;

import com.ssafy.companyanalysis.agent.domain.Evidence;
import tools.jackson.databind.JsonNode;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * AI 가 준 근거 블록을 {@link Evidence} 로 옮긴다.
 *
 * <p>AI 는 근거에 발행 시각을 통째로 주는데 화면은 연도만 쓴다. 날짜 형식이 바뀌어도 터지지
 * 않도록 앞 네 자리가 숫자일 때만 연도로 읽고, 아니면 비워 둔다.
 */
final class EvidenceMapper {

    private static final int MAX_SNIPPET = 1_000;

    private EvidenceMapper() {
    }

    /** 총괄·담당이 주는 {@code evidence[]} 배열. */
    static List<Evidence> fromArray(JsonNode array) {
        if (array == null || !array.isArray()) {
            return List.of();
        }
        Set<String> seen = new LinkedHashSet<>();
        List<Evidence> evidences = new ArrayList<>();
        for (JsonNode node : array) {
            String key = text(node, "evidence_id");
            if (!key.isBlank() && !seen.add(key)) {
                continue;
            }
            evidences.add(new Evidence(
                    nullable(node, "source_type"),
                    nullable(node, "title"),
                    year(text(node, "date")),
                    null,
                    trimmed(nullable(node, "excerpt")),
                    nullable(node, "url")));
        }
        return List.copyOf(evidences);
    }

    /**
     * 뉴스 담당을 직접 부른 응답에는 {@code evidence[]} 가 없다. 신호마다 달린 인용 기사
     * ({@code analysis.signals[].sources[]})가 같은 자리를 대신한다.
     */
    static List<Evidence> fromNewsSignals(JsonNode analysis) {
        JsonNode signals = analysis == null ? null : analysis.path("signals");
        if (signals == null || !signals.isArray()) {
            return List.of();
        }
        Set<String> seen = new LinkedHashSet<>();
        List<Evidence> evidences = new ArrayList<>();
        for (JsonNode signal : signals) {
            for (JsonNode source : signal.path("sources")) {
                String key = text(source, "article_id");
                if (!key.isBlank() && !seen.add(key)) {
                    continue;
                }
                evidences.add(new Evidence(
                        "NEWS_ARTICLE",
                        nullable(source, "title"),
                        year(text(source, "published_at")),
                        null,
                        trimmed(nullable(signal, "summary")),
                        nullable(source, "url")));
            }
        }
        return List.copyOf(evidences);
    }

    private static Integer year(String isoDate) {
        if (isoDate.length() < 4) {
            return null;
        }
        String head = isoDate.substring(0, 4);
        return head.chars().allMatch(Character::isDigit) ? Integer.valueOf(head) : null;
    }

    private static String trimmed(String value) {
        if (value == null) {
            return null;
        }
        return value.length() > MAX_SNIPPET ? value.substring(0, MAX_SNIPPET) : value;
    }

    private static String text(JsonNode node, String field) {
        return node.path(field).asString("");
    }

    private static String nullable(JsonNode node, String field) {
        String value = text(node, field);
        return value.isBlank() ? null : value;
    }
}

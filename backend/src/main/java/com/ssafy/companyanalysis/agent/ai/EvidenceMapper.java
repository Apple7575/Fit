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
    private static final String DART_DOCUMENT_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=";

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

    /**
     * 기업 담당을 직접 부른 응답에는 {@code evidence[]} 가 없다. 서술에 달린 인용
     * ({@code citations[]})이 같은 자리를 대신한다. 파이썬 총괄의 변환과 같은 규칙이다.
     *
     * <p>접수번호가 있으면 DART 원문 링크를 만들고 앞 네 자리를 연도로 쓴다. 기사와 달리
     * 인용마다 제목이 없으므로 기업명을 제목으로 둔다 — 화면에서 출처를 구분할 이름이 필요하다.
     */
    static List<Evidence> fromCompanyCitations(JsonNode citations, String corpName) {
        if (citations == null || !citations.isArray()) {
            return List.of();
        }
        Set<String> seen = new LinkedHashSet<>();
        List<Evidence> evidences = new ArrayList<>();
        for (JsonNode node : citations) {
            String sourceId = text(node, "source_id");
            if (sourceId.isBlank() || !seen.add(sourceId)) {
                continue;
            }
            String receipt = text(node, "rcept_no");
            evidences.add(new Evidence(
                    nullable(node, "source_type"),
                    corpName == null || corpName.isBlank() ? null : corpName,
                    year(receipt),
                    null,
                    trimmed(nullable(node, "excerpt")),
                    receipt.isBlank() ? null : DART_DOCUMENT_URL + receipt));
        }
        return List.copyOf(evidences);
    }

    /**
     * 리포트의 {@code sources[]} → 근거. 인용과 달리 제목·발행일·링크가 이미 들어 있어
     * 그대로 옮긴다. 리포트가 통째로 한 말풍선이라 근거도 보고서 단위다.
     */
    static List<Evidence> fromCompanyReportSources(JsonNode sources, String corpName) {
        if (sources == null || !sources.isArray()) {
            return List.of();
        }
        Set<String> seen = new LinkedHashSet<>();
        List<Evidence> evidences = new ArrayList<>();
        for (JsonNode node : sources) {
            String receipt = text(node, "rcept_no");
            if (!receipt.isBlank() && !seen.add(receipt)) {
                continue;
            }
            String title = text(node, "title");
            evidences.add(new Evidence(
                    "DART_BUSINESS_REPORT",
                    title.isBlank() ? (corpName == null || corpName.isBlank() ? null : corpName) : title,
                    year(text(node, "published_at")),
                    null,
                    null,
                    nullable(node, "url")));
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

package com.ssafy.companyanalysis.agent.ai;

import tools.jackson.databind.JsonNode;

import java.util.ArrayList;
import java.util.List;

/**
 * 담당별 결과 블록을 화면에 띄울 한 덩어리 글로 옮긴다.
 *
 * <p>담당마다 응답 모양이 다르다. 포지션·글쓰기·뉴스는 사람이 읽을 {@code message} 를 직접
 * 주지만, 채용공고 담당은 요구사항별 판정만 준다. 여기서 그 차이를 흡수해 말풍선 하나에
 * 들어갈 글로 만든다.
 */
final class AgentResultText {

    /** 공고 요구사항을 다 늘어놓으면 말풍선이 화면을 넘긴다. 못 채운 것부터 몇 개만 보인다. */
    private static final int JD_LINE_LIMIT = 5;

    private AgentResultText() {
    }

    static String of(String agent, JsonNode result) {
        if (result == null || !result.isObject()) {
            return "";
        }
        return switch (agent) {
            case "jd" -> jd(result);
            case "writing" -> writing(result);
            default -> result.path("message").asString("");
        };
    }

    /** 수정문은 제안일 뿐이므로 초안으로 자동 승격하지 않는다. 수락은 사용자가 따로 한다. */
    private static String writing(JsonNode result) {
        String message = result.path("message").asString("");
        String revised = result.path("revision").path("revised_text").asString("");
        if (revised.isBlank()) {
            return message;
        }
        return message.isBlank() ? revised : message + "\n[제안] " + revised;
    }

    /**
     * 못 채운 요구사항이 먼저 보여야 고칠 것을 안다. 미충족 → 일부 충족 순으로 세우고 충족한
     * 것은 개수로만 알린다.
     */
    private static String jd(JsonNode result) {
        // 사용자가 물었으면 담당이 그 질문에 답한 message 를 함께 준다. 그때는 대조 목록을
        // 다시 그리지 않는다 — 무엇을 묻든 같은 목록이 돌아오면 대화가 되지 않는다.
        String answer = result.path("message").asString("");
        if (!answer.isBlank()) {
            return answer;
        }

        JsonNode summary = result.path("summary");
        List<String> lines = new ArrayList<>();
        lines.add("공고 요구사항 대조 — 충족 %d · 일부 충족 %d · 미충족 %d".formatted(
                summary.path("supported").asInt(0),
                summary.path("partially_supported").asInt(0),
                summary.path("not_supported").asInt(0)));

        List<JsonNode> requirements = new ArrayList<>();
        collect(result.path("requirements"), "NOT_SUPPORTED", requirements);
        collect(result.path("requirements"), "PARTIALLY_SUPPORTED", requirements);
        requirements.stream().limit(JD_LINE_LIMIT).forEach(node -> lines.add(
                "- %s: %s".formatted(
                        node.path("requirement").asString("요구사항"),
                        node.path("feedback").asString(""))));

        if (requirements.isEmpty()) {
            lines.add("공고가 요구하는 항목은 자소서에서 모두 확인됐습니다.");
        } else if (requirements.size() > JD_LINE_LIMIT) {
            lines.add("이 밖에 %d건이 더 있습니다.".formatted(requirements.size() - JD_LINE_LIMIT));
        }
        return String.join("\n", lines);
    }

    private static void collect(JsonNode requirements, String label, List<JsonNode> into) {
        if (!requirements.isArray()) {
            return;
        }
        for (JsonNode node : requirements) {
            if (label.equals(node.path("label").asString(""))) {
                into.add(node);
            }
        }
    }
}

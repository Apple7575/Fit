package com.ssafy.companyanalysis.interview.ai;

import java.util.List;
import java.util.Map;

/**
 * 구조화 출력 JSON 스키마. 논리 구조는 같고 타입 표기만 다르다
 * (OpenAI/vLLM 은 소문자 object/string, Gemini 는 대문자 OBJECT/STRING).
 */
final class InterviewSchema {

    private InterviewSchema() {
    }

    /** questions: [{ question, sourceType }] */
    static Map<String, Object> questions(String typeCase) {
        Casing c = new Casing(typeCase);
        Map<String, Object> question = c.object(
                Map.<String, Object>of(
                        "question", c.string(),
                        "sourceType", c.stringEnum("company", "cover_letter", "common")),
                List.of("question", "sourceType"));
        return c.object(
                Map.<String, Object>of("questions", c.array(question)),
                List.of("questions"));
    }

    /** { overallSummary, items: [{ feedbackSummary, points: [{ kind, category, message, suggestion }] }] } */
    static Map<String, Object> evaluation(String typeCase) {
        Casing c = new Casing(typeCase);
        Map<String, Object> point = c.object(
                Map.<String, Object>of(
                        "kind", c.stringEnum("STRENGTH", "IMPROVEMENT"),
                        "category", c.stringEnum("질문적합성", "구체성", "논리성", "기업직무이해", "전달력"),
                        "message", c.string(),
                        "suggestion", c.string()),
                List.of("kind", "category", "message"));
        Map<String, Object> item = c.object(
                Map.<String, Object>of(
                        "feedbackSummary", c.string(),
                        "points", c.array(point)),
                List.of("feedbackSummary", "points"));
        return c.object(
                Map.<String, Object>of(
                        "overallSummary", c.string(),
                        "items", c.array(item)),
                List.of("overallSummary", "items"));
    }

    /** { needed, question, basis } — needed=false 면 더 물을 가치가 없다는 신호로, question 은 비운다. */
    static Map<String, Object> followup(String typeCase) {
        Casing c = new Casing(typeCase);
        return c.object(
                Map.<String, Object>of("needed", c.bool(), "question", c.string(), "basis", c.string()),
                List.of("needed", "question"));
    }

    /** 타입 표기(대/소문자)만 다른 스키마 조각을 만든다. */
    private record Casing(boolean upper) {

        Casing(String typeCase) {
            this("upper".equals(typeCase));
        }

        Map<String, Object> object(Map<String, Object> properties, List<String> required) {
            return Map.<String, Object>of(
                    "type", upper ? "OBJECT" : "object", "properties", properties, "required", required);
        }

        Map<String, Object> array(Map<String, Object> items) {
            return Map.<String, Object>of("type", upper ? "ARRAY" : "array", "items", items);
        }

        Map<String, Object> string() {
            return Map.<String, Object>of("type", upper ? "STRING" : "string");
        }

        Map<String, Object> bool() {
            return Map.<String, Object>of("type", upper ? "BOOLEAN" : "boolean");
        }

        Map<String, Object> stringEnum(String... values) {
            return Map.<String, Object>of("type", upper ? "STRING" : "string", "enum", List.of(values));
        }
    }
}

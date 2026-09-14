package com.ssafy.companyanalysis.agent.domain;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 자소서를 함께 검토하는 에이전트 6종.
 *
 * <p>테이블로 두지 않고 상수로 둔다. 이름·담당 자료·프롬프트는 코드를 고칠 때만 바뀌는데,
 * DB 에 두면 코드와 DB 두 군데를 맞춰야 한다.
 *
 * <p>{@link #SUPERVISOR} 만 {@code selectable = false} 다. 사용자가 직접 넣는 대상이 아니라
 * 에이전트가 2명 이상일 때 서버가 자동으로 붙인다 — 혼자 있는 방에는 조정할 것이 없다.
 */
public enum AgentType {

    JD("jd", "채용공고 담당", "채용공고 필수 자격요건의 누락 여부를 점검합니다.",
            "채용공고 원문(웹 크롤링)", true,
            schema("jdUrl", new ConfigField("string", true, "채용공고 URL"))),

    COMPANY("company", "기업 RAG 담당", "기업의 사업 방향과 강점의 부합 여부를 분석합니다.",
            "기업별 Vector DB(사업보고서 · IR)", true,
            schema("corpCodes", new ConfigField("array", true, "분석 대상 기업의 corpCode 목록. 복수 선택"))),

    POSITION("position", "포지션 담당", "직무 요구 수준에 맞는 기술적 깊이를 검증합니다.",
            "직무별 지식베이스(기술 스택 · CS · 아키텍처)", true,
            schema("jobRole", new ConfigField("enum", true, "지원 직무. /api/job-roles 의 key"))),

    NEWS("news", "뉴스/트렌드 담당", "설득력을 높여줄 최근 기업 이슈 및 트렌드를 제안합니다.",
            "최근 뉴스", true,
            schema("corpCodes", new ConfigField("array", true, "대상 기업의 corpCode 목록"),
                    "months", new ConfigField("number", false, "몇 개월치를 볼지. 기본 6"))),

    WRITING("writing", "글쓰기 담당", "가독성, 두괄식 구성, 글자 수 및 중복 표현을 교정합니다.",
            "자소서 원문", true,
            schema()),

    SUPERVISOR("supervisor", "총괄", "다른 에이전트의 지적을 종합해 최우선 수정 과제를 낸다",
            "다른 에이전트의 출력", false,
            schema());

    private final String key;
    private final String displayName;
    private final String description;
    private final String dataSource;
    private final boolean selectable;
    private final Map<String, ConfigField> configSchema;

    AgentType(String key, String displayName, String description, String dataSource,
              boolean selectable, Map<String, ConfigField> configSchema) {
        this.key = key;
        this.displayName = displayName;
        this.description = description;
        this.dataSource = dataSource;
        this.selectable = selectable;
        this.configSchema = configSchema;
    }

    /**
     * 필수 설정이 다 찼는지. 방은 자소서를 고르면 설정 없이 자동으로 만들어지므로,
     * 덜 채운 상태가 정상이다. 실제로 돌리기 직전에 이걸로 거른다.
     */
    public boolean isConfigured(Map<String, Object> config) {
        Map<String, Object> given = config == null ? Map.of() : config;
        return configSchema.entrySet().stream()
                .filter(entry -> entry.getValue().required())
                .allMatch(entry -> isPresent(given.get(entry.getKey())));
    }

    /** 비어 있는 설정에서 빠진 필수 항목 이름. 화면에 무엇을 채우라고 알려줄 때 쓴다. */
    public java.util.List<String> missingConfigKeys(Map<String, Object> config) {
        Map<String, Object> given = config == null ? Map.of() : config;
        return configSchema.entrySet().stream()
                .filter(entry -> entry.getValue().required())
                .filter(entry -> !isPresent(given.get(entry.getKey())))
                .map(Map.Entry::getKey)
                .toList();
    }

    private static boolean isPresent(Object value) {
        if (value == null) {
            return false;
        }
        if (value instanceof String text) {
            return !text.isBlank();
        }
        if (value instanceof java.util.Collection<?> collection) {
            return !collection.isEmpty();
        }
        return true;
    }

    /** 키로 찾는다. 모르는 키는 비어 있는 값으로 돌려주고 호출부가 400 을 낸다. */
    public static java.util.Optional<AgentType> from(String key) {
        return java.util.Arrays.stream(values()).filter(type -> type.key.equals(key)).findFirst();
    }

    /** 설정 항목은 화면에 나열되는 순서가 있어 {@link LinkedHashMap} 으로 만든다. */
    private static Map<String, ConfigField> schema(Object... keyThenField) {
        Map<String, ConfigField> built = new LinkedHashMap<>();
        for (int i = 0; i < keyThenField.length; i += 2) {
            built.put((String) keyThenField[i], (ConfigField) keyThenField[i + 1]);
        }
        return Collections.unmodifiableMap(built);
    }

    public String key() {
        return key;
    }

    public String displayName() {
        return displayName;
    }

    public String description() {
        return description;
    }

    public String dataSource() {
        return dataSource;
    }

    public boolean selectable() {
        return selectable;
    }

    public Map<String, ConfigField> configSchema() {
        return configSchema;
    }
}

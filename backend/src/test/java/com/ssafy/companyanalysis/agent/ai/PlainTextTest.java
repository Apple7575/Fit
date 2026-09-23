package com.ssafy.companyanalysis.agent.ai;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

/** 말풍선에 넣기 전 마크다운 걷어 내기. 화면은 글자를 그대로 보여 준다. */
class PlainTextTest {

    @Test
    @DisplayName("굵게·기울임·코드 기호를 떼고 글자만 남긴다")
    void stripsInlineMarks() {
        assertThat(PlainText.of("**핵심**은 *수치*와 `API` 입니다"))
                .isEqualTo("핵심은 수치와 API 입니다");
    }

    @Test
    @DisplayName("제목 기호를 떼고 목록은 • 로 바꾼다")
    void convertsHeadingsAndBullets() {
        assertThat(PlainText.of("## 요약\n\n- 첫째\n* 둘째\n  + 셋째"))
                .isEqualTo("요약\n\n• 첫째\n• 둘째\n  • 셋째");
    }

    @Test
    @DisplayName("표는 구분선을 버리고 한 행을 한 줄로 편다")
    void flattensTables() {
        assertThat(PlainText.of("| 항목 | 2024 | 2025 |\n| --- | :---: | ---: |\n| 매출 | 10 | 12 |"))
                .isEqualTo("• 항목: 2024 · 2025\n• 매출: 10 · 12");
    }

    @Test
    @DisplayName("링크는 글자와 주소를, 인용·구분선·코드 울타리는 기호만 걷어 낸다")
    void stripsLinksQuotesRulesAndFences() {
        assertThat(PlainText.of("> 인용\n---\n```java\nint a;\n```\n[공시](https://dart.fss.or.kr)"))
                .isEqualTo("인용\nint a;\n공시 (https://dart.fss.or.kr)");
    }

    @Test
    @DisplayName("곱셈·식별자·음수처럼 기호가 뜻인 글자는 건드리지 않는다")
    void keepsMeaningfulSymbols() {
        String text = "3*4 = 12, snake_case 변수, -3% 감소, 1. 첫 항목";
        assertThat(PlainText.of(text)).isEqualTo(text);
    }

    @Test
    @DisplayName("빈 줄이 셋 이상 이어지면 하나로 줄인다")
    void collapsesBlankRuns() {
        assertThat(PlainText.of("가\n\n\n\n나")).isEqualTo("가\n\n나");
    }

    @Test
    @DisplayName("이미 평문이면 그대로 둔다")
    void keepsPlainText() {
        String text = "자격요건 중 하나가 빠져 있어요.\n\n• 수치를 넣어 주세요.";
        assertThat(PlainText.of(text)).isEqualTo(text);
    }
}

package com.ssafy.companyanalysis.global.text;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class PlainTextTest {

    @Test
    @DisplayName("별표 강조는 기호만 벗기고 글자는 남긴다")
    void strongMarkersAreStripped() {
        assertThat(PlainText.of("**두괄식**으로 올리세요")).isEqualTo("두괄식으로 올리세요");
        assertThat(PlainText.of("__꼭__ 고치세요")).isEqualTo("꼭 고치세요");
        assertThat(PlainText.of("*강조* 합니다")).isEqualTo("강조 합니다");
    }

    @Test
    @DisplayName("제목 표시는 줄 앞의 우물정만 뗀다")
    void headingMarkersAreStripped() {
        assertThat(PlainText.of("## 요약\n결론이 뒤에 있습니다")).isEqualTo("요약\n결론이 뒤에 있습니다");
        assertThat(PlainText.of("###없는 공백도 처리")).isEqualTo("없는 공백도 처리");
    }

    @Test
    @DisplayName("백틱과 인용 표시도 벗긴다")
    void codeAndQuoteMarkersAreStripped() {
        assertThat(PlainText.of("`Kafka` 경험을 쓰세요")).isEqualTo("Kafka 경험을 쓰세요");
        assertThat(PlainText.of("> 인용한 문장")).isEqualTo("인용한 문장");
    }

    @Test
    @DisplayName("목록 표시는 남긴다 — 읽기 좋은 구분이라 지울 이유가 없다")
    void listMarkersSurvive() {
        String text = "고칠 곳:\n- 첫 문장\n- 마지막 문단\n* 별표 목록";

        assertThat(PlainText.of(text)).isEqualTo(text);
    }

    @Test
    @DisplayName("밑줄은 건드리지 않는다 — 식별자를 망가뜨린다")
    void underscoresInWordsSurvive() {
        assertThat(PlainText.of("corp_code 를 맞추세요")).isEqualTo("corp_code 를 맞추세요");
        assertThat(PlainText.of("agent_room 과 agent_message")).isEqualTo("agent_room 과 agent_message");
    }

    @Test
    @DisplayName("곱셈이나 각주로 쓴 별표 하나는 건드리지 않는다")
    void loneAsteriskSurvives() {
        assertThat(PlainText.of("2 * 3 은 6 이다")).isEqualTo("2 * 3 은 6 이다");
    }

    @Test
    @DisplayName("기호를 떼고 남은 빈 줄을 접는다")
    void blankRunsAreCollapsed() {
        assertThat(PlainText.of("## 제목\n\n\n\n본문")).isEqualTo("제목\n\n본문");
    }

    @Test
    @DisplayName("빈 값은 그대로 돌려준다")
    void blankIsLeftAlone() {
        assertThat(PlainText.of(null)).isNull();
        assertThat(PlainText.of("   ")).isEqualTo("   ");
    }

    @Test
    @DisplayName("벗긴 뒤에도 원문 속 인용은 그대로 찾을 수 있다")
    void strippedTextStillMatchesSource() {
        String answer = "저는 Kafka 컨슈머를 직접 구성해 초당 3천 건을 처리했습니다.";

        // 문항 피드백의 quote 는 벗기지 않지만, 총평·코멘트에 인용이 섞여도 글자가 사라지면 안 된다.
        assertThat(PlainText.of("**Kafka 컨슈머를 직접 구성**해 부분이 좋습니다"))
                .isEqualTo("Kafka 컨슈머를 직접 구성해 부분이 좋습니다");
        assertThat(answer).contains("Kafka 컨슈머를 직접 구성");
    }
}

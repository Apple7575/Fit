package com.ssafy.companyanalysis.agent.crawl;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

/** 네트워크를 타지 않는 부분(HTML → 평문)만 본다. 실제 조회는 사이트가 바뀌면 깨지므로 테스트하지 않는다. */
class JobPostingFetcherTest {

    @Test
    @DisplayName("스크립트와 스타일은 본문에서 빼낸다")
    void scriptAndStyleAreRemoved() {
        String html = """
                <html><head><style>.a{color:red}</style></head>
                <body><script>var x = '자격요건';</script><p>주요업무</p></body></html>
                """;

        String text = JobPostingFetcher.toText(html);

        assertThat(text).contains("주요업무");
        assertThat(text).doesNotContain("color:red");
        assertThat(text).doesNotContain("var x");
    }

    @Test
    @DisplayName("블록 태그는 줄바꿈으로 바꿔 항목 구분을 남긴다")
    void blockTagsBecomeLineBreaks() {
        String html = "<ul><li>경력 5년 이상</li><li>학력무관</li></ul>";

        assertThat(JobPostingFetcher.toText(html).lines()).containsExactly("경력 5년 이상", "학력무관");
    }

    @Test
    @DisplayName("HTML 엔티티를 원래 글자로 되돌린다")
    void entitiesAreDecoded() {
        String text = JobPostingFetcher.toText("<p>Java&nbsp;&amp;&nbsp;Spring &lt;필수&gt;</p>");

        assertThat(text).isEqualTo("Java & Spring <필수>");
    }

    @Test
    @DisplayName("연속된 공백과 빈 줄을 접는다 — 프롬프트에 들어갈 글자라 낭비하지 않는다")
    void whitespaceIsCollapsed() {
        String html = "<div>주요업무</div>\n\n\n<div>   자격요건   </div>";

        assertThat(JobPostingFetcher.toText(html)).isEqualTo("주요업무\n자격요건");
    }
}

package com.ssafy.companyanalysis.global.text;

import java.util.regex.Pattern;

/**
 * 모델 답변에서 마크다운 기호를 걷어낸다.
 *
 * <p>화면은 답변을 평문 그대로 뿌린다. 마크다운을 그리지 않으므로 {@code **강조**} 나
 * {@code ## 제목} 이 기호째 보인다. 프롬프트로 쓰지 말라고 이르지만 모델이 자주 어겨서
 * 받은 쪽에서 한 번 더 지운다.
 *
 * <p><b>글자를 지우지 않고 기호만 벗긴다.</b> 표시가 잘못 걸려도 내용은 남아야 한다.
 */
public final class PlainText {

    /** ## 제목. 줄 앞의 # 만 뗀다. */
    private static final Pattern HEADING = Pattern.compile("(?m)^\\s{0,3}#{1,6}\\s*");

    /** **강조** 와 __강조__. 안쪽 글자는 남긴다. */
    private static final Pattern STRONG = Pattern.compile("(\\*\\*|__)(?=\\S)(.+?)(?<=\\S)\\1", Pattern.DOTALL);

    /**
     * *기울임*. 줄머리 목록 표시(`* 항목`)와 헷갈리지 않게 앞뒤가 공백이 아닐 때만 본다.
     * 밑줄(_)은 건드리지 않는다 — corp_code 같은 식별자를 망가뜨린다.
     */
    private static final Pattern EMPHASIS = Pattern.compile("(?<![\\w*])\\*(?=\\S)([^*\\n]+?)(?<=\\S)\\*(?![\\w*])");

    /** `코드`. 답변에 코드가 나올 일은 드물고, 백틱이 그대로 보이는 편이 더 어색하다. */
    private static final Pattern CODE = Pattern.compile("`+([^`\\n]+?)`+");

    /** > 인용. 줄 앞의 꺾쇠만 뗀다. */
    private static final Pattern QUOTE = Pattern.compile("(?m)^\\s{0,3}>\\s?");

    /** 세 줄 이상 이어진 빈 줄. 기호를 떼고 나면 남는다. */
    private static final Pattern BLANK_RUN = Pattern.compile("\n{3,}");

    private PlainText() {
    }

    public static String of(String text) {
        if (text == null || text.isBlank()) {
            return text;
        }
        String cleaned = CODE.matcher(text).replaceAll("$1");
        cleaned = STRONG.matcher(cleaned).replaceAll("$2");
        cleaned = EMPHASIS.matcher(cleaned).replaceAll("$1");
        cleaned = HEADING.matcher(cleaned).replaceAll("");
        cleaned = QUOTE.matcher(cleaned).replaceAll("");
        cleaned = BLANK_RUN.matcher(cleaned).replaceAll("\n\n");
        return cleaned.trim();
    }
}

package com.ssafy.companyanalysis.agent.ai;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 말풍선에 넣기 전에 마크다운 기호를 걷어 낸다.
 *
 * <p>화면은 줄바꿈만 살려 글자를 그대로 보여 준다. 모델이 {@code **굵게**}·{@code ## 제목}·표를
 * 쓰면 기호가 글자로 박혀 읽기 어렵다. 프롬프트로도 막지만 모델이 늘 지키지는 않아 저장 직전에
 * 한 번 더 거른다.
 *
 * <p>뜻이 있는 모양은 남긴다. 목록은 "• " 로, 표의 한 행은 "• 첫 칸: 나머지 칸" 으로 바꾼다.
 * 이미 평문인 글은 그대로 나온다.
 */
public final class PlainText {

    private static final Pattern FENCE = Pattern.compile("^\\s*(```|~~~).*$");
    private static final Pattern HEADING = Pattern.compile("^\\s{0,3}#{1,6}\\s+(.*?)\\s*#*\\s*$");
    private static final Pattern BULLET = Pattern.compile("^(\\s*)[-*+]\\s+(.*)$");
    private static final Pattern QUOTE = Pattern.compile("^\\s*>\\s?(.*)$");
    private static final Pattern RULE = Pattern.compile("^\\s*([-*_])(\\s*\\1){2,}\\s*$");
    private static final Pattern TABLE_SEPARATOR =
            Pattern.compile("^\\s*\\|?\\s*:?-{3,}:?\\s*(\\|\\s*:?-{3,}:?\\s*)*\\|?\\s*$");
    private static final Pattern TABLE_ROW = Pattern.compile("^\\s*\\|(.*)\\|\\s*$");

    private static final Pattern IMAGE = Pattern.compile("!\\[([^\\]]*)]\\(([^)\\s]+)\\)");
    private static final Pattern LINK = Pattern.compile("\\[([^\\]]+)]\\(([^)\\s]+)\\)");
    private static final Pattern BOLD = Pattern.compile("(\\*\\*|__)(?=\\S)(.+?)(?<=\\S)\\1");
    /** 곱셈("3*4")이나 식별자("snake_case")는 건드리지 않도록 양옆이 글자가 아닐 때만 본다. */
    private static final Pattern ITALIC = Pattern.compile("(?<![\\w*])\\*(?=\\S)([^*\\n]+?)(?<=\\S)\\*(?![\\w*])");
    private static final Pattern CODE = Pattern.compile("`([^`\\n]+)`");
    private static final Pattern BLANK_RUN = Pattern.compile("\\n{3,}");

    private PlainText() {
    }

    public static String of(String text) {
        if (text == null || text.isBlank()) {
            return text;
        }
        List<String> lines = new ArrayList<>();
        for (String line : text.replace("\r\n", "\n").split("\n", -1)) {
            String converted = line(line);
            if (converted != null) {
                lines.add(inline(converted));
            }
        }
        return BLANK_RUN.matcher(String.join("\n", lines)).replaceAll("\n\n").strip();
    }

    /** 줄 단위 기호. null 이면 그 줄을 버린다. */
    private static String line(String line) {
        if (FENCE.matcher(line).matches() || RULE.matcher(line).matches()
                || TABLE_SEPARATOR.matcher(line).matches() && line.contains("-") && line.contains("|")) {
            return null;
        }
        Matcher heading = HEADING.matcher(line);
        if (heading.matches()) {
            return heading.group(1);
        }
        Matcher quote = QUOTE.matcher(line);
        if (quote.matches()) {
            line = quote.group(1);
        }
        Matcher row = TABLE_ROW.matcher(line);
        if (row.matches()) {
            return tableRow(row.group(1));
        }
        Matcher bullet = BULLET.matcher(line);
        if (bullet.matches()) {
            return bullet.group(1) + "• " + bullet.group(2);
        }
        return line;
    }

    private static String tableRow(String inner) {
        List<String> cells = new ArrayList<>();
        for (String cell : inner.split("\\|", -1)) {
            if (!cell.isBlank()) {
                cells.add(cell.strip());
            }
        }
        if (cells.isEmpty()) {
            return null;
        }
        if (cells.size() == 1) {
            return "• " + cells.get(0);
        }
        return "• " + cells.get(0) + ": " + String.join(" · ", cells.subList(1, cells.size()));
    }

    private static String inline(String line) {
        String out = IMAGE.matcher(line).replaceAll("$1");
        out = LINK.matcher(out).replaceAll("$1 ($2)");
        out = BOLD.matcher(out).replaceAll("$2");
        out = ITALIC.matcher(out).replaceAll("$1");
        out = CODE.matcher(out).replaceAll("$1");
        // 짝이 맞지 않아 남은 굵게 기호. 문장에 "**" 를 쓸 일은 없다.
        return out.replace("**", "");
    }
}

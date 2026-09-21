package com.ssafy.companyanalysis.agent.ai;

import tools.jackson.databind.JsonNode;

import java.util.ArrayList;
import java.util.List;
import java.util.StringJoiner;

/**
 * 기업 분석 리포트(구조화 JSON)를 말풍선에 넣을 마크다운으로 푼다.
 *
 * <p>메시지가 담을 수 있는 것은 문자열 하나라 표·차트를 그대로 넘길 자리가 없다. 표는 마크다운
 * 표로 옮기고, 차트는 같은 값을 표로 편다 — 차트와 표는 같은 숫자를 다르게 보여 줄 뿐이라
 * 이렇게 해도 정보가 빠지지 않는다.
 *
 * <p>인용은 붙이지 않는다. 블록마다 근거가 달려 있어 그대로 옮기면 본문보다 길어진다. 근거는
 * 메시지의 {@code evidences} 자리에 따로 싣는다.
 */
final class CompanyReportText {

    private static final int MAX_TABLE_ROWS = 30;

    private CompanyReportText() {
    }

    static String of(JsonNode report) {
        StringBuilder out = new StringBuilder();
        String name = report.path("corp_name").asString("");
        int year = report.path("fiscal_year").asInt(0);
        out.append("## ").append(name.isBlank() ? "기업 분석" : name + " 기업 분석");
        if (year > 0) {
            out.append(" (").append(year).append("년 기준)");
        }
        out.append("\n\n");

        String intro = report.path("intro").path("text").asString("");
        if (!intro.isBlank()) {
            out.append(intro).append("\n\n");
        }

        for (JsonNode section : report.path("sections")) {
            String title = section.path("title").asString("");
            if (!title.isBlank()) {
                out.append("### ").append(title).append("\n\n");
            }
            for (JsonNode block : section.path("blocks")) {
                String rendered = block(block);
                if (!rendered.isBlank()) {
                    out.append(rendered).append("\n");
                }
            }
        }

        String sources = sources(report.path("sources"));
        if (!sources.isBlank()) {
            out.append(sources);
        }
        return out.toString().strip();
    }

    private static String block(JsonNode block) {
        return switch (block.path("kind").asString("")) {
            case "text" -> text(block);
            case "bullets" -> bullets(block);
            case "kpi" -> kpi(block);
            case "table" -> table(block);
            case "chart" -> chart(block);
            case "swot" -> swot(block);
            default -> "";
        };
    }

    private static String text(JsonNode block) {
        String body = block.path("text").asString("");
        if (body.isBlank()) {
            return "";
        }
        return heading(block) + body + "\n";
    }

    private static String bullets(JsonNode block) {
        StringBuilder out = new StringBuilder(heading(block));
        for (JsonNode item : block.path("items")) {
            String line = item.path("text").asString("");
            if (!line.isBlank()) {
                out.append("- ").append(line).append("\n");
            }
        }
        return out.length() == heading(block).length() ? "" : out.toString();
    }

    /** 카드 한 장이 한 줄이다. 증감률은 부호를 살려 "+6.3%" 로 쓴다. */
    private static String kpi(JsonNode block) {
        StringBuilder out = new StringBuilder(heading(block));
        for (JsonNode item : block.path("items")) {
            String label = item.path("label").asString("");
            if (label.isBlank()) {
                continue;
            }
            out.append("- **").append(label).append("**: ")
                    .append(number(item.path("value")))
                    .append(item.path("unit").asString(""));
            JsonNode delta = item.path("delta_pct");
            if (delta.isNumber()) {
                double value = delta.asDouble();
                out.append(" (전년 대비 ").append(value >= 0 ? "+" : "").append(number(delta)).append("%)");
            }
            String note = item.path("note").asString("");
            if (!note.isBlank()) {
                out.append(" — ").append(note);
            }
            out.append("\n");
        }
        return out.length() == heading(block).length() ? "" : out.toString();
    }

    private static String table(JsonNode block) {
        List<String> columns = new ArrayList<>();
        for (JsonNode column : block.path("columns")) {
            columns.add(column.asString(""));
        }
        if (columns.isEmpty()) {
            return "";
        }
        StringBuilder out = new StringBuilder(heading(block));
        String unit = block.path("unit").asString("");
        if (!unit.isBlank()) {
            out.append("(단위: ").append(unit).append(")\n\n");
        }
        out.append(row(columns));
        out.append(separator(columns.size()));
        int printed = 0;
        for (JsonNode row : block.path("rows")) {
            if (printed++ >= MAX_TABLE_ROWS) {
                out.append("\n…(이하 생략)\n");
                break;
            }
            List<String> cells = new ArrayList<>();
            for (JsonNode cell : row) {
                cells.add(number(cell));
            }
            out.append(row(cells));
        }
        return out.append("\n").toString();
    }

    /**
     * 차트는 그릴 수 없으므로 같은 값을 표로 편다. 가로축이 열, 계열이 행이다 — 계열 이름이
     * 길어 행으로 두어야 읽힌다.
     */
    private static String chart(JsonNode block) {
        List<String> categories = new ArrayList<>();
        for (JsonNode category : block.path("categories")) {
            categories.add(category.asString(""));
        }
        if (categories.isEmpty()) {
            return "";
        }
        StringBuilder out = new StringBuilder(heading(block));
        String unit = block.path("unit").asString("");
        if (!unit.isBlank()) {
            out.append("(단위: ").append(unit).append(")\n\n");
        }
        List<String> header = new ArrayList<>();
        header.add("구분");
        header.addAll(categories);
        out.append(row(header));
        out.append(separator(header.size()));
        for (JsonNode series : block.path("series")) {
            List<String> cells = new ArrayList<>();
            cells.add(series.path("name").asString(""));
            for (JsonNode value : series.path("values")) {
                cells.add(number(value));
            }
            out.append(row(cells));
        }
        return out.append("\n").toString();
    }

    private static String swot(JsonNode block) {
        StringBuilder out = new StringBuilder();
        appendQuadrant(out, block, "strengths", "강점");
        appendQuadrant(out, block, "weaknesses", "약점");
        appendQuadrant(out, block, "opportunities", "기회");
        appendQuadrant(out, block, "threats", "위협");
        return out.toString();
    }

    private static void appendQuadrant(StringBuilder out, JsonNode block, String field, String label) {
        JsonNode quadrant = block.path(field);
        if (quadrant.isMissingNode() || quadrant.isNull()) {
            return;
        }
        String headline = quadrant.path("headline").asString("");
        out.append("**").append(label);
        if (!headline.isBlank()) {
            out.append(" — ").append(headline);
        }
        out.append("**\n");
        String summary = quadrant.path("summary").asString("");
        if (!summary.isBlank()) {
            out.append(summary).append("\n");
        }
        for (JsonNode item : quadrant.path("items")) {
            String line = item.path("text").asString("");
            if (!line.isBlank()) {
                out.append("- ").append(line).append("\n");
            }
        }
        out.append("\n");
    }

    private static String sources(JsonNode sources) {
        if (!sources.isArray() || sources.isEmpty()) {
            return "";
        }
        StringBuilder out = new StringBuilder("### 출처\n\n");
        for (JsonNode source : sources) {
            String title = source.path("title").asString("");
            String url = source.path("url").asString("");
            if (title.isBlank() && url.isBlank()) {
                continue;
            }
            out.append("- ").append(title.isBlank() ? url : title);
            if (!url.isBlank() && !title.isBlank()) {
                out.append(" (").append(url).append(")");
            }
            out.append("\n");
        }
        return out.toString();
    }

    private static String heading(JsonNode block) {
        String title = block.path("title").asString("");
        return title.isBlank() ? "" : "**" + title + "**\n\n";
    }

    private static String row(List<String> cells) {
        StringJoiner joiner = new StringJoiner(" | ", "| ", " |\n");
        cells.forEach(joiner::add);
        return joiner.toString();
    }

    private static String separator(int size) {
        StringJoiner joiner = new StringJoiner(" | ", "| ", " |\n");
        for (int index = 0; index < size; index++) {
            joiner.add("---");
        }
        return joiner.toString();
    }

    /** 정수로 떨어지는 실수는 소수점을 떼야 표가 읽힌다(186.0 → 186). */
    private static String number(JsonNode node) {
        if (node == null || node.isNull() || node.isMissingNode()) {
            return "";
        }
        if (!node.isNumber()) {
            return node.asString("");
        }
        double value = node.asDouble();
        if (value == Math.rint(value) && Math.abs(value) < 1e15) {
            return String.valueOf((long) value);
        }
        return String.valueOf(value);
    }
}

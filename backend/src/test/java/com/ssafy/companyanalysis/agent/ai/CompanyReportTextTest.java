package com.ssafy.companyanalysis.agent.ai;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 리포트(구조화 JSON) → 말풍선 평문.
 *
 * <p>표본은 실제 응답({@code GET /company/internal/reports/00164742})에서 블록 종류마다 하나씩
 * 추린 것이다. 필드 이름이 바뀌면 여기서 먼저 깨진다.
 */
class CompanyReportTextTest {

    private static final JsonMapper MAPPER = JsonMapper.builder().build();

    @Test
    @DisplayName("섹션 제목과 본문을 순서대로 펼친다")
    void rendersSectionsInOrder() {
        String rendered = CompanyReportText.of(report("""
                {"corp_name":"현대자동차","fiscal_year":2025,
                 "intro":{"text":"자동차 제조 기업입니다."},
                 "sections":[{"type":"BUSINESS","title":"사업 내용","blocks":[
                   {"kind":"text","title":"주요 사업","text":"승용차와 상용차를 만듭니다."},
                   {"kind":"bullets","items":[{"text":"**차량부문**: 78.2%"}]}]}],
                 "sources":[]}
                """));

        assertThat(rendered).startsWith("현대자동차 기업 분석 (2025년 기준)");
        assertThat(rendered).contains("자동차 제조 기업입니다.");
        assertThat(rendered).contains("■ 사업 내용");
        assertThat(rendered).contains("[주요 사업]");
        assertThat(rendered).contains("• 차량부문: 78.2%");
        assertThat(rendered).doesNotContain("**").doesNotContain("#");
    }

    @Test
    @DisplayName("표는 한 행을 한 줄로 펴고 단위를 소제목 뒤에 적는다")
    void rendersTableAsLines() {
        String rendered = CompanyReportText.of(report("""
                {"corp_name":"현대자동차","fiscal_year":2025,"sections":[{"title":"재무","blocks":[
                  {"kind":"table","title":"재무 추이","columns":["항목","2024년","2025년"],
                   "rows":[["매출액",175.2,186.3]],"unit":"조원"}]}],"sources":[]}
                """));

        assertThat(rendered).contains("[재무 추이] (단위: 조원)");
        assertThat(rendered).contains("• 매출액: 2024년 175.2 · 2025년 186.3");
        assertThat(rendered).doesNotContain("|");
    }

    @Test
    @DisplayName("차트는 그릴 수 없으므로 같은 값을 줄로 편다")
    void rendersChartAsTable() {
        String rendered = CompanyReportText.of(report("""
                {"corp_name":"현대자동차","fiscal_year":2025,"sections":[{"title":"재무","blocks":[
                  {"kind":"chart","title":"매출 추이","chart":"bar","categories":["2024","2025"],
                   "series":[{"name":"매출액","values":[175.2,186.3]}],"unit":"조원"}]}],"sources":[]}
                """));

        assertThat(rendered).contains("• 매출액: 2024 175.2 · 2025 186.3");
    }

    @Test
    @DisplayName("KPI 는 증감률의 부호를 살린다")
    void rendersKpiWithSignedDelta() {
        String rendered = CompanyReportText.of(report("""
                {"corp_name":"현대자동차","fiscal_year":2025,"sections":[{"title":"사업","blocks":[
                  {"kind":"kpi","items":[
                    {"label":"2025년 매출","value":186.3,"unit":"조원","delta_pct":6.3},
                    {"label":"2025년 영업이익","value":11.5,"unit":"조원","delta_pct":-19.5}]}]}],"sources":[]}
                """));

        assertThat(rendered).contains("• 2025년 매출: 186.3조원 (전년 대비 +6.3%)");
        assertThat(rendered).contains("• 2025년 영업이익: 11.5조원 (전년 대비 -19.5%)");
    }

    @Test
    @DisplayName("SWOT 은 사분면마다 머리글과 항목을 편다")
    void rendersSwotQuadrants() {
        String rendered = CompanyReportText.of(report("""
                {"corp_name":"현대자동차","fiscal_year":2025,"sections":[{"title":"SWOT","blocks":[
                  {"kind":"swot",
                   "strengths":{"headline":"강력한 시장 지위","summary":"매출이 늘고 있습니다.",
                                "items":[{"text":"**매출 성장**: 6.3% 증가"}]},
                   "weaknesses":{"headline":"수익성 하락","summary":"영업이익이 줄었습니다.","items":[]},
                   "opportunities":null,"threats":null}]}],"sources":[]}
                """));

        assertThat(rendered).contains("[강점] 강력한 시장 지위");
        assertThat(rendered).contains("• 매출 성장: 6.3% 증가");
        assertThat(rendered).contains("[약점] 수익성 하락");
        assertThat(rendered).doesNotContain("[기회]");
    }

    @Test
    @DisplayName("정수로 떨어지는 값은 소수점을 떼어 표가 읽히게 한다")
    void dropsTrailingZeroDecimals() {
        String rendered = CompanyReportText.of(report("""
                {"corp_name":"A","fiscal_year":2025,"sections":[{"title":"재무","blocks":[
                  {"kind":"table","columns":["항목","값"],"rows":[["직원 수",72598.0]]}]}],"sources":[]}
                """));

        assertThat(rendered).contains("• 직원 수: 72598");
    }

    @Test
    @DisplayName("출처는 제목과 링크를 함께 적는다")
    void rendersSources() {
        String rendered = CompanyReportText.of(report("""
                {"corp_name":"현대자동차","fiscal_year":2025,"sections":[],
                 "sources":[{"rcept_no":"20260318001394","title":"사업보고서 (2025.12)",
                             "url":"https://dart.fss.or.kr/x"}]}
                """));

        assertThat(rendered).contains("■ 출처");
        assertThat(rendered).contains("• 사업보고서 (2025.12) (https://dart.fss.or.kr/x)");
    }

    private static JsonNode report(String json) {
        return MAPPER.readTree(json);
    }
}

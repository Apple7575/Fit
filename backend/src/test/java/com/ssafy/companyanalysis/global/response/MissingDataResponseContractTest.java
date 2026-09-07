package com.ssafy.companyanalysis.global.response;

import com.ssafy.companyanalysis.company.controller.CompanyController;
import com.ssafy.companyanalysis.company.dto.CompanyDetailResponse;
import com.ssafy.companyanalysis.company.dto.CompanyProfileResponse;
import com.ssafy.companyanalysis.company.dto.CompanySearchResponse;
import com.ssafy.companyanalysis.company.service.CompanyDetailService;
import com.ssafy.companyanalysis.company.service.CompanyProfileService;
import com.ssafy.companyanalysis.company.service.CompanySearchService;
import com.ssafy.companyanalysis.comparison.controller.IndustryCompaniesController;
import com.ssafy.companyanalysis.comparison.controller.IndustryComparisonController;
import com.ssafy.companyanalysis.comparison.dto.IndustryCompaniesResponse;
import com.ssafy.companyanalysis.comparison.dto.IndustryComparisonResponse;
import com.ssafy.companyanalysis.comparison.service.IndustryCompaniesService;
import com.ssafy.companyanalysis.comparison.service.IndustryComparisonService;
import com.ssafy.companyanalysis.focus.controller.CompanyActivitiesController;
import com.ssafy.companyanalysis.focus.controller.CompanyFocusController;
import com.ssafy.companyanalysis.focus.controller.CompanySegmentsController;
import com.ssafy.companyanalysis.focus.dto.CompanyActivitiesResponse;
import com.ssafy.companyanalysis.focus.dto.CompanyFocusResponse;
import com.ssafy.companyanalysis.focus.dto.CompanySegmentsResponse;
import com.ssafy.companyanalysis.focus.service.CompanyActivityService;
import com.ssafy.companyanalysis.focus.service.CompanyFocusService;
import com.ssafy.companyanalysis.focus.service.CompanySegmentsService;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.metric.controller.CompanyMetricController;
import com.ssafy.companyanalysis.metric.dto.CompanyMetricsResponse;
import com.ssafy.companyanalysis.metric.dto.MetricPointResponse;
import com.ssafy.companyanalysis.metric.dto.MetricRangeResponse;
import com.ssafy.companyanalysis.metric.dto.MetricSeriesResponse;
import com.ssafy.companyanalysis.metric.dto.MetricTimeseriesResponse;
import com.ssafy.companyanalysis.metric.dto.MetricValueResponse;
import com.ssafy.companyanalysis.metric.dto.ProfitabilityResponse;
import com.ssafy.companyanalysis.metric.service.CompanyMetricService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 결측·부분 데이터 응답 기준(S15P21A504-100)을 엔드포인트 전체에 걸쳐 고정한다.
 *
 * <p>규칙 원문은 {@code docs/decisions/0001-missing-data-response.md} 에 있다.
 * 컨트롤러별 테스트가 각자의 화면 관점에서 결측을 확인한다면, 여기서는 엔드포인트 전체가
 * <b>같은 규칙</b>으로 움직이는지를 본다. 응답 봉투·Jackson 설정처럼 한 번 바뀌면
 * 전부 한꺼번에 깨지는 지점을 한 자리에서 잡기 위해서다.
 *
 * <p>기업 개요(S15P21A504-97)와 집중 분야 세 건(S15P21A504-98)까지 들어왔다. 최근 이슈
 * API(S15P21A504-99)가 붙을 때도 같은 형태의 케이스를 여기에 추가한다.
 */
@WebMvcTest({CompanyController.class, CompanyMetricController.class,
        IndustryComparisonController.class, IndustryCompaniesController.class,
        CompanyFocusController.class, CompanySegmentsController.class,
        CompanyActivitiesController.class})
class MissingDataResponseContractTest {

    private static final String CORP_CODE = "00164779";

    /** 비교 지표 7종(v2). IndustryComparisonService 가 정한 순서와 같다. */
    private static final List<String> COMPARISON_METRICS = List.of(
            "revenue", "revenue_growth", "operating_profit", "operating_margin",
            "employee_count", "average_salary", "rd_ratio");

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private CompanySearchService companySearchService;

    @MockitoBean
    private CompanyDetailService companyDetailService;

    @MockitoBean
    private CompanyProfileService companyProfileService;

    @MockitoBean
    private CompanyMetricService companyMetricService;

    @MockitoBean
    private IndustryComparisonService industryComparisonService;

    @MockitoBean
    private IndustryCompaniesService industryCompaniesService;

    @MockitoBean
    private CompanyFocusService companyFocusService;

    @MockitoBean
    private CompanySegmentsService companySegmentsService;

    @MockitoBean
    private CompanyActivityService companyActivityService;

    @Test
    @DisplayName("규칙1 - 검색 결과가 없는 것은 오류가 아니라 빈 배열이다")
    void emptySearchResultIsNotAnError() throws Exception {
        given(companySearchService.search(anyString(), anyInt(), anyInt()))
                .willReturn(new CompanySearchResponse(List.of(), 0));

        mockMvc.perform(get("/api/companies").param("keyword", "없는기업"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.items", hasSize(0)))
                .andExpect(jsonPath("$.data.total").value(0))
                .andExpect(jsonPath("$.error").doesNotExist());
    }

    @Test
    @DisplayName("규칙2 - 값이 없는 필드도 키는 남고 null 로 나간다 (필드 생략 금지)")
    void missingFieldsKeepTheirKeys() throws Exception {
        // 이름만 아는 기업. 산업·대표자·설립일·주소·홈페이지·기준연도가 전부 비어 있다.
        given(companyDetailService.getCompany(CORP_CODE))
                .willReturn(new CompanyDetailResponse(CORP_CODE, "이름만있는기업",
                        null, null, null, null, null, null, null));

        mockMvc.perform(get("/api/companies/{corpCode}", CORP_CODE))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.industryCode").hasJsonPath())
                .andExpect(jsonPath("$.data.industryCode").value(nullValue()))
                .andExpect(jsonPath("$.data.industryName").hasJsonPath())
                .andExpect(jsonPath("$.data.industryName").value(nullValue()))
                .andExpect(jsonPath("$.data.ceo").hasJsonPath())
                .andExpect(jsonPath("$.data.ceo").value(nullValue()))
                .andExpect(jsonPath("$.data.establishedDate").hasJsonPath())
                .andExpect(jsonPath("$.data.establishedDate").value(nullValue()))
                .andExpect(jsonPath("$.data.address").hasJsonPath())
                .andExpect(jsonPath("$.data.address").value(nullValue()))
                .andExpect(jsonPath("$.data.homepageUrl").hasJsonPath())
                .andExpect(jsonPath("$.data.homepageUrl").value(nullValue()))
                .andExpect(jsonPath("$.data.dataYear").hasJsonPath())
                .andExpect(jsonPath("$.data.dataYear").value(nullValue()));
    }

    @Test
    @DisplayName("규칙3 - 없는 값을 0 으로 바꾸지 않는다 (0 원과 미공시는 다른 사실이다)")
    void missingValueIsNotZero() throws Exception {
        given(companyMetricService.getMetrics(eq(CORP_CODE), any(), any()))
                .willReturn(new CompanyMetricsResponse(CORP_CODE, 2025, List.of(
                        new MetricValueResponse("operating_profit", "영업이익", BigDecimal.ZERO, "KRW", null),
                        new MetricValueResponse("net_income", "당기순이익", null, "KRW", null)),
                        new ProfitabilityResponse(BigDecimal.ZERO, null, null)));

        mockMvc.perform(get("/api/companies/{corpCode}/metrics", CORP_CODE))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.metrics[0].value").value(0))
                .andExpect(jsonPath("$.data.metrics[1].value").hasJsonPath())
                .andExpect(jsonPath("$.data.metrics[1].value").value(nullValue()))
                // 비율도 같은 규칙이다. 0 은 그대로 0 이고, 못 내는 값은 null 이다.
                .andExpect(jsonPath("$.data.profitability.operatingMargin").value(0))
                .andExpect(jsonPath("$.data.profitability.netMargin").hasJsonPath())
                .andExpect(jsonPath("$.data.profitability.netMargin").value(nullValue()));
    }

    @Test
    @DisplayName("규칙4 - 적재값이 하나도 없어도 200 이고, 기준연도만 null 이며 골격은 유지된다")
    void emptyCompanyStillReturnsFullSkeleton() throws Exception {
        given(companyMetricService.getMetrics(eq(CORP_CODE), any(), any()))
                .willReturn(new CompanyMetricsResponse(CORP_CODE, null, emptyMetrics(),
                        new ProfitabilityResponse(null, null, null)));

        mockMvc.perform(get("/api/companies/{corpCode}/metrics", CORP_CODE))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.year").hasJsonPath())
                .andExpect(jsonPath("$.data.year").value(nullValue()))
                .andExpect(jsonPath("$.data.metrics", hasSize(6)))
                .andExpect(jsonPath("$.data.metrics[0].key").value("revenue"))
                .andExpect(jsonPath("$.data.metrics[0].unit").value("KRW"))
                .andExpect(jsonPath("$.data.metrics[0].value").value(nullValue()))
                .andExpect(jsonPath("$.data.metrics[5].key").value("average_tenure"))
                .andExpect(jsonPath("$.data.metrics[5].value").value(nullValue()))
                // 계산할 원본이 하나도 없어도 블록을 생략하지 않는다.
                .andExpect(jsonPath("$.data.profitability").hasJsonPath())
                .andExpect(jsonPath("$.data.profitability.debtRatio").hasJsonPath())
                .andExpect(jsonPath("$.data.profitability.debtRatio").value(nullValue()));
    }

    @Test
    @DisplayName("규칙5 - 시계열은 값이 없는 해도 연도 자리를 비우지 않는다")
    void timeseriesKeepsEveryYearSlot() throws Exception {
        given(companyMetricService.getTimeseries(eq(CORP_CODE), any(), any(), any()))
                .willReturn(new MetricTimeseriesResponse(
                        new MetricRangeResponse(2021, 2025),
                        List.of(new MetricSeriesResponse("revenue", "매출액", "KRW", List.of(
                                new MetricPointResponse(2021, null, null),
                                new MetricPointResponse(2022, null, null),
                                new MetricPointResponse(2023, new BigDecimal("258900000000000"), null),
                                new MetricPointResponse(2024, null, null),
                                new MetricPointResponse(2025, null, null))))));

        mockMvc.perform(get("/api/companies/{corpCode}/metrics/timeseries", CORP_CODE))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.range.from").value(2021))
                .andExpect(jsonPath("$.data.range.to").value(2025))
                .andExpect(jsonPath("$.data.series[0].points", hasSize(5)))
                .andExpect(jsonPath("$.data.series[0].points[0].year").value(2021))
                .andExpect(jsonPath("$.data.series[0].points[0].value").hasJsonPath())
                .andExpect(jsonPath("$.data.series[0].points[0].value").value(nullValue()))
                .andExpect(jsonPath("$.data.series[0].points[2].value").value(258900000000000L));
    }

    @Test
    @DisplayName("규칙5 - 비교군이 없어도 대상 기업과 지표 4종의 자리는 유지된다")
    void comparisonKeepsTargetAndMetricSlots() throws Exception {
        given(industryComparisonService.compare(eq(CORP_CODE), any(), any(), any()))
                .willReturn(new IndustryComparisonResponse(
                        null,
                        new IndustryComparisonResponse.Industry(null, null, 1),
                        COMPARISON_METRICS,
                        List.of(new IndustryComparisonResponse.Company(
                                CORP_CODE, "비교군없는기업", true, emptyComparisonValues()))));

        mockMvc.perform(get("/api/companies/{corpCode}/industry-comparison", CORP_CODE))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.year").hasJsonPath())
                .andExpect(jsonPath("$.data.year").value(nullValue()))
                .andExpect(jsonPath("$.data.industry.code").hasJsonPath())
                .andExpect(jsonPath("$.data.industry.code").value(nullValue()))
                .andExpect(jsonPath("$.data.metrics", hasSize(7)))
                .andExpect(jsonPath("$.data.companies", hasSize(1)))
                .andExpect(jsonPath("$.data.companies[0].isTarget").value(true))
                .andExpect(jsonPath("$.data.companies[0].values.revenue").hasJsonPath())
                .andExpect(jsonPath("$.data.companies[0].values.revenue").value(nullValue()))
                .andExpect(jsonPath("$.data.companies[0].values.average_salary").hasJsonPath())
                .andExpect(jsonPath("$.data.companies[0].values.average_salary").value(nullValue()));
    }

    @Test
    @DisplayName("규칙1·2 - 없는 산업의 후보 목록은 오류가 아니라 industry null 과 빈 배열이다")
    void unknownIndustryReturnsEmptyCandidateList() throws Exception {
        given(industryCompaniesService.listCandidates(eq("99"), any(), anyInt()))
                .willReturn(new IndustryCompaniesResponse(null, List.of()));

        mockMvc.perform(get("/api/industries/{industryCode}/companies", "99"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                // 산업을 못 찾아도 키는 남는다. 프론트가 null 과 "필드 없음"을 구분하지 않아도 되게.
                .andExpect(jsonPath("$.data.industry").hasJsonPath())
                .andExpect(jsonPath("$.data.industry").value(nullValue()))
                .andExpect(jsonPath("$.data.companies", hasSize(0)))
                .andExpect(jsonPath("$.error").doesNotExist());
    }

    @Test
    @DisplayName("규칙4 - 개요가 한 해도 적재되지 않아도 200 이고 목록은 null 이 아니라 빈 배열이다")
    void emptyProfileKeepsArraysAndReturnsOk() throws Exception {
        given(companyProfileService.getProfile(eq(CORP_CODE), any()))
                .willReturn(new CompanyProfileResponse(null, List.of(), List.of(), null, List.of()));

        mockMvc.perform(get("/api/companies/{corpCode}/profile", CORP_CODE))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.year").hasJsonPath())
                .andExpect(jsonPath("$.data.year").value(nullValue()))
                // 목록이 비면 빈 배열이지 null 이 아니다.
                .andExpect(jsonPath("$.data.businesses", hasSize(0)))
                .andExpect(jsonPath("$.data.segments", hasSize(0)))
                .andExpect(jsonPath("$.data.products", hasSize(0)))
                .andExpect(jsonPath("$.data.totalRevenue").hasJsonPath())
                .andExpect(jsonPath("$.data.totalRevenue").value(nullValue()))
                .andExpect(jsonPath("$.error").doesNotExist());
    }

    @Test
    @DisplayName("규칙2·3 - 매출 미공시 부문도 자리를 지키고 0 이 아니라 null 로 나간다")
    void undisclosedSegmentKeepsKeysAndStaysNull() throws Exception {
        given(companyProfileService.getProfile(eq(CORP_CODE), any()))
                .willReturn(new CompanyProfileResponse(2025,
                        List.of("반도체"),
                        List.of(new CompanyProfileResponse.Segment("SDC", null, null)),
                        null,
                        List.of()));

        mockMvc.perform(get("/api/companies/{corpCode}/profile", CORP_CODE))
                .andExpect(status().isOk())
                // 부문이 존재한다는 사실은 남기고 값만 비운다. 목록에서 빼면 부문 수가 달라진다.
                .andExpect(jsonPath("$.data.segments", hasSize(1)))
                .andExpect(jsonPath("$.data.segments[0].code").value("SDC"))
                .andExpect(jsonPath("$.data.segments[0].revenue").hasJsonPath())
                .andExpect(jsonPath("$.data.segments[0].revenue").value(nullValue()))
                .andExpect(jsonPath("$.data.segments[0].revenueShare").hasJsonPath())
                .andExpect(jsonPath("$.data.segments[0].revenueShare").value(nullValue()))
                // 공시된 부문 매출이 없으면 합계도 0 이 아니라 null 이다.
                .andExpect(jsonPath("$.data.totalRevenue").value(nullValue()));
    }

    @Test
    @DisplayName("규칙4 - 집중 분야는 한쪽 출처만 비어도 두 블록의 골격을 모두 유지한다")
    void focusKeepsBothBlocksWhenOneSourceIsEmpty() throws Exception {
        // 사업 방향 분석은 아직 안 돌았고 R&D 비용만 적재된 기업.
        given(companyFocusService.getFocus(eq(CORP_CODE), any()))
                .willReturn(new CompanyFocusResponse(2025,
                        new CompanyFocusResponse.Direction(List.of(), List.of(), null),
                        new CompanyFocusResponse.Rnd(
                                new BigDecimal("37000000000000"), null, null, List.of())));

        mockMvc.perform(get("/api/companies/{corpCode}/focus", CORP_CODE))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                // 비어 있는 블록을 null 로 접지 않는다. 조건부 표시는 화면이 판단한다.
                .andExpect(jsonPath("$.data.direction").hasJsonPath())
                .andExpect(jsonPath("$.data.direction.newBusiness", hasSize(0)))
                .andExpect(jsonPath("$.data.direction.keywords", hasSize(0)))
                .andExpect(jsonPath("$.data.direction.strategyChange").hasJsonPath())
                .andExpect(jsonPath("$.data.direction.strategyChange").value(nullValue()))
                .andExpect(jsonPath("$.data.rnd.expense").value(37000000000000L))
                .andExpect(jsonPath("$.data.rnd.growthRate").hasJsonPath())
                .andExpect(jsonPath("$.data.rnd.growthRate").value(nullValue()))
                .andExpect(jsonPath("$.data.rnd.fields", hasSize(0)));
    }

    @Test
    @DisplayName("규칙3 - 부문 인력 증감은 감소도 사실이라 음수를 0 으로 바꾸지 않는다")
    void segmentDecreaseStaysNegative() throws Exception {
        given(companySegmentsService.getSegments(eq(CORP_CODE), any()))
                .willReturn(new CompanySegmentsResponse(2025, -500, List.of(
                        new CompanySegmentsResponse.Segment("DX", null, null, -1000),
                        new CompanySegmentsResponse.Segment("SDC", null, null, null))));

        mockMvc.perform(get("/api/companies/{corpCode}/segments", CORP_CODE))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.employeeTotalChange").value(-500))
                .andExpect(jsonPath("$.data.segments[0].employeeChange").value(-1000))
                // 줄어든 것과 공시하지 않은 것은 다른 사실이다.
                .andExpect(jsonPath("$.data.segments[1].employeeChange").hasJsonPath())
                .andExpect(jsonPath("$.data.segments[1].employeeChange").value(nullValue()));
    }

    @Test
    @DisplayName("규칙1 - 투자 공시가 없는 기업은 오류가 아니라 빈 배열이다")
    void emptyActivitiesIsNotAnError() throws Exception {
        given(companyActivityService.getActivities(eq(CORP_CODE), anyString(), any(), any()))
                .willReturn(new CompanyActivitiesResponse(List.of()));

        mockMvc.perform(get("/api/companies/{corpCode}/activities", CORP_CODE)
                        .param("type", "facility"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.items", hasSize(0)))
                .andExpect(jsonPath("$.error").doesNotExist());
    }

    @Test
    @DisplayName("규칙6 - 기업 자체가 없는 것은 결측이 아니라 404 COMPANY_NOT_FOUND 다")
    void unknownCompanyIsNotTreatedAsMissingData() throws Exception {
        given(companyMetricService.getMetrics(anyString(), any(), any()))
                .willThrow(new BusinessException(ErrorCode.COMPANY_NOT_FOUND));

        mockMvc.perform(get("/api/companies/{corpCode}/metrics", "00000000"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.error.code").value("COMPANY_NOT_FOUND"))
                .andExpect(jsonPath("$.data").doesNotExist());
    }

    @Test
    @DisplayName("규칙6 - 서버 오류는 빈 데이터로 위장하지 않고 500 INTERNAL_ERROR 로 나간다")
    void serverFailureIsNotDisguisedAsEmptyData() throws Exception {
        willThrow(new IllegalStateException("connection reset"))
                .given(industryComparisonService).compare(anyString(), any(), any(), any());

        mockMvc.perform(get("/api/companies/{corpCode}/industry-comparison", CORP_CODE))
                .andExpect(status().isInternalServerError())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.error.code").value("INTERNAL_ERROR"))
                .andExpect(jsonPath("$.data").doesNotExist());
    }

    /** 값이 하나도 없는 기업의 지표 6종 골격. metric 카탈로그의 display_order 순서다. */
    private static List<MetricValueResponse> emptyMetrics() {
        return List.of(
                new MetricValueResponse("revenue", "매출액", null, "KRW", null),
                new MetricValueResponse("operating_profit", "영업이익", null, "KRW", null),
                new MetricValueResponse("net_income", "당기순이익", null, "KRW", null),
                new MetricValueResponse("employee_count", "직원 수", null, "PERSON", null),
                new MetricValueResponse("average_salary", "1인 평균 급여", null, "KRW", null),
                new MetricValueResponse("average_tenure", "평균 근속", null, "YEAR", null));
    }

    /** 비교 지표 4종을 순서대로 null 로 채운 맵. */
    private static Map<String, BigDecimal> emptyComparisonValues() {
        Map<String, BigDecimal> values = new LinkedHashMap<>();
        for (String code : COMPARISON_METRICS) {
            values.put(code, null);
        }
        return values;
    }
}

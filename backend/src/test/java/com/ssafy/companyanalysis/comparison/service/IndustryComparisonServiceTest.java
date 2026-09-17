package com.ssafy.companyanalysis.comparison.service;

import com.ssafy.companyanalysis.company.repository.CompanyDetailProjection;
import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.comparison.dto.IndustryComparisonResponse;
import com.ssafy.companyanalysis.comparison.repository.IndustryComparisonProjection;
import com.ssafy.companyanalysis.comparison.repository.IndustryComparisonRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.global.year.BaseYearResolver;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;

class IndustryComparisonServiceTest {

    private static final String TARGET = "00164779";
    private static final String PEER = "00126380";

    /** v2 명세의 비교 지표 7종. 응답 순서가 이 순서여야 한다. */
    private static final List<String> METRICS_V2 = List.of(
            "revenue", "revenue_growth", "operating_profit", "operating_margin",
            "employee_count", "average_salary", "rd_ratio");

    /** 기준연도 계산은 BaseYearResolverTest 가 맡는다. 여기서는 고정값을 준다. */
    private static final int BASE_YEAR = 2025;

    private CompanyRepository companyRepository;
    private IndustryComparisonRepository comparisonRepository;
    private BaseYearResolver baseYearResolver;
    private IndustryComparisonService service;

    @BeforeEach
    void setUp() {
        companyRepository = mock(CompanyRepository.class);
        comparisonRepository = mock(IndustryComparisonRepository.class);
        baseYearResolver = mock(BaseYearResolver.class);
        given(baseYearResolver.resolve()).willReturn(BASE_YEAR);
        service = new IndustryComparisonService(companyRepository, comparisonRepository, baseYearResolver);
    }

    @Test
    @DisplayName("지표를 지정하지 않으면 v2 의 7종을 순서대로 내보낸다")
    void defaultsToSevenMetricsInSpecOrder() {
        CompanyDetailProjection target = target("26", "전자 부품 제조업");
        given(companyRepository.findDetailByCorpCode(TARGET)).willReturn(Optional.of(target));
        given(comparisonRepository.findValues(any(), any(), anyInt(), anyInt())).willReturn(List.of());

        IndustryComparisonResponse response = service.compare(TARGET, null, null, 2025);

        assertThat(response.metrics()).containsExactlyElementsOf(METRICS_V2);
        assertThat(response.companies().getFirst().values().keySet())
                .containsExactlyElementsOf(METRICS_V2);
    }

    @Test
    @DisplayName("대상 기업과 고른 peers 만 담고, 대상 기업이 맨 앞이다")
    void includesTargetAndChosenPeersOnly() {
        CompanyDetailProjection target = target("26", "전자 부품 제조업");
        List<IndustryComparisonProjection> rows = List.of(
                row(TARGET, "SK하이닉스", "revenue", 2025, new BigDecimal("71000000000000.0000"), (short) 0),
                row(PEER, "삼성전자", "revenue", 2025, new BigDecimal("300870000000000.0000"), (short) 0));
        given(companyRepository.findDetailByCorpCode(TARGET)).willReturn(Optional.of(target));
        given(comparisonRepository.findValues(any(), any(), anyInt(), anyInt())).willReturn(rows);

        IndustryComparisonResponse response = service.compare(TARGET, List.of(PEER), null, 2025);

        assertThat(response.companies()).hasSize(2);
        assertThat(response.companies().get(0).corpCode()).isEqualTo(TARGET);
        assertThat(response.companies().get(0).isTarget()).isTrue();
        assertThat(response.companies().get(0).values().get("revenue"))
                .isEqualByComparingTo("71000000000000");
        assertThat(response.companies().get(1).corpCode()).isEqualTo(PEER);
        assertThat(response.companies().get(1).isTarget()).isFalse();
    }

    @Test
    @DisplayName("매출 성장률은 요청 연도와 전년 매출로 계산한다")
    void revenueGrowthUsesPreviousYear() {
        CompanyDetailProjection target = target("26", "전자 부품 제조업");
        List<IndustryComparisonProjection> rows = List.of(
                row(TARGET, "SK하이닉스", "revenue", 2025, new BigDecimal("120.0000"), (short) 0),
                row(TARGET, "SK하이닉스", "revenue", 2024, new BigDecimal("100.0000"), (short) 0));
        given(companyRepository.findDetailByCorpCode(TARGET)).willReturn(Optional.of(target));
        given(comparisonRepository.findValues(any(), any(), eq(2025), eq(2024))).willReturn(rows);

        IndustryComparisonResponse response = service.compare(TARGET, null, null, 2025);

        assertThat(response.companies().getFirst().values().get("revenue_growth"))
                .isEqualByComparingTo("20.0");
    }

    @Test
    @DisplayName("전년 매출이 없으면 성장률은 null 이고 매출 자체는 그대로 나간다")
    void revenueGrowthIsNullWithoutPreviousYear() {
        CompanyDetailProjection target = target("26", "전자 부품 제조업");
        List<IndustryComparisonProjection> rows = List.of(
                row(TARGET, "SK하이닉스", "revenue", 2025, new BigDecimal("120.0000"), (short) 0));
        given(companyRepository.findDetailByCorpCode(TARGET)).willReturn(Optional.of(target));
        given(comparisonRepository.findValues(any(), any(), anyInt(), anyInt())).willReturn(rows);

        IndustryComparisonResponse response = service.compare(TARGET, null, null, 2025);

        assertThat(response.companies().getFirst().values()).containsKey("revenue_growth");
        assertThat(response.companies().getFirst().values().get("revenue_growth")).isNull();
        assertThat(response.companies().getFirst().values().get("revenue")).isEqualByComparingTo("120");
    }

    @Test
    @DisplayName("영업이익률은 영업이익 나누기 매출이고, 적자면 음수 그대로 나간다")
    void operatingMarginAllowsNegativeProfit() {
        CompanyDetailProjection target = target("26", "전자 부품 제조업");
        List<IndustryComparisonProjection> rows = List.of(
                row(TARGET, "SK하이닉스", "revenue", 2025, new BigDecimal("1000.0000"), (short) 0),
                row(TARGET, "SK하이닉스", "operating_profit", 2025, new BigDecimal("-50.0000"), (short) 0));
        given(companyRepository.findDetailByCorpCode(TARGET)).willReturn(Optional.of(target));
        given(comparisonRepository.findValues(any(), any(), anyInt(), anyInt())).willReturn(rows);

        IndustryComparisonResponse response = service.compare(TARGET, null, null, 2025);

        assertThat(response.companies().getFirst().values().get("operating_margin"))
                .isEqualByComparingTo("-5.0");
    }

    @Test
    @DisplayName("매출이 없으면 영업이익률은 null 이다")
    void operatingMarginIsNullWithoutRevenue() {
        CompanyDetailProjection target = target("26", "전자 부품 제조업");
        List<IndustryComparisonProjection> rows = List.of(
                row(TARGET, "SK하이닉스", "operating_profit", 2025, new BigDecimal("50.0000"), (short) 0));
        given(companyRepository.findDetailByCorpCode(TARGET)).willReturn(Optional.of(target));
        given(comparisonRepository.findValues(any(), any(), anyInt(), anyInt())).willReturn(rows);

        IndustryComparisonResponse response = service.compare(TARGET, null, null, 2025);

        assertThat(response.companies().getFirst().values()).containsKey("operating_margin");
        assertThat(response.companies().getFirst().values().get("operating_margin")).isNull();
    }

    @Test
    @DisplayName("파생 지표만 요청해도 원본 지표를 조회에 넣는다")
    void derivedMetricsQueryTheirSources() {
        CompanyDetailProjection target = target("26", "전자 부품 제조업");
        given(companyRepository.findDetailByCorpCode(TARGET)).willReturn(Optional.of(target));
        given(comparisonRepository.findValues(any(), any(), anyInt(), anyInt())).willReturn(List.of());

        service.compare(TARGET, null, List.of("operating_margin"), 2025);

        then(comparisonRepository).should().findValues(
                List.of(TARGET), java.util.Set.of("operating_profit", "revenue"), 2025, 2024);
    }

    @Test
    @DisplayName("지표를 고르면 그 지표만, 명세 순서로 내보낸다")
    void selectedMetricsKeepSpecOrder() {
        CompanyDetailProjection target = target("26", "전자 부품 제조업");
        given(companyRepository.findDetailByCorpCode(TARGET)).willReturn(Optional.of(target));
        given(comparisonRepository.findValues(any(), any(), anyInt(), anyInt())).willReturn(List.of());

        IndustryComparisonResponse response =
                service.compare(TARGET, null, List.of("rd_ratio", "revenue"), 2025);

        assertThat(response.metrics()).containsExactly("revenue", "rd_ratio");
    }

    @Test
    @DisplayName("7종 밖의 지표는 METRIC_NOT_SUPPORTED 다")
    void unsupportedMetricThrows() {
        CompanyDetailProjection target = target("26", "전자 부품 제조업");
        given(companyRepository.findDetailByCorpCode(TARGET)).willReturn(Optional.of(target));

        assertThatThrownBy(() -> service.compare(TARGET, null, List.of("average_tenure"), 2025))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.METRIC_NOT_SUPPORTED);
    }

    @Test
    @DisplayName("peers 가 3개를 넘으면 INVALID_PARAMETER 다")
    void tooManyPeersThrows() {
        CompanyDetailProjection target = target("26", "전자 부품 제조업");
        given(companyRepository.findDetailByCorpCode(TARGET)).willReturn(Optional.of(target));

        assertThatThrownBy(() -> service.compare(TARGET, List.of("1", "2", "3", "4"), null, 2025))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.INVALID_PARAMETER);
    }

    @Test
    @DisplayName("peers 의 중복과 대상 기업 자신은 빼고 세므로 3개를 넘지 않는다")
    void duplicatePeersAndSelfAreDropped() {
        CompanyDetailProjection target = target("26", "전자 부품 제조업");
        given(companyRepository.findDetailByCorpCode(TARGET)).willReturn(Optional.of(target));
        given(comparisonRepository.findValues(any(), any(), anyInt(), anyInt())).willReturn(List.of());

        service.compare(TARGET, List.of(PEER, PEER, TARGET, "  "), null, 2025);

        then(comparisonRepository).should().findValues(
                eq(List.of(TARGET, PEER)), any(), anyInt(), anyInt());
    }

    @Test
    @DisplayName("조회에서 빠진 peer 는 목록에도 없다")
    void unknownPeerIsDroppedFromResult() {
        CompanyDetailProjection target = target("26", "전자 부품 제조업");
        List<IndustryComparisonProjection> rows = List.of(
                row(TARGET, "SK하이닉스", "revenue", 2025, new BigDecimal("100.0000"), (short) 0));
        given(companyRepository.findDetailByCorpCode(TARGET)).willReturn(Optional.of(target));
        given(comparisonRepository.findValues(any(), any(), anyInt(), anyInt())).willReturn(rows);

        IndustryComparisonResponse response = service.compare(TARGET, List.of("99999999"), null, 2025);

        assertThat(response.companies()).hasSize(1);
        assertThat(response.companies().getFirst().corpCode()).isEqualTo(TARGET);
    }

    @Test
    @DisplayName("companyCount 는 응답에 실린 수가 아니라 산업 전체 기업 수다")
    void companyCountIsWholeIndustry() {
        CompanyDetailProjection target = target("26", "전자 부품 제조업");
        given(companyRepository.findDetailByCorpCode(TARGET)).willReturn(Optional.of(target));
        given(comparisonRepository.findValues(any(), any(), anyInt(), anyInt())).willReturn(List.of());
        given(comparisonRepository.countByIndustry("26")).willReturn(42L);

        IndustryComparisonResponse response = service.compare(TARGET, null, null, 2025);

        assertThat(response.companies()).hasSize(1);
        assertThat(response.industry().companyCount()).isEqualTo(42);
    }

    @Test
    @DisplayName("산업이 없는 기업은 companyCount 를 세지 않고 0 이다")
    void companyCountIsZeroWithoutIndustry() {
        CompanyDetailProjection target = target(null, null);
        given(companyRepository.findDetailByCorpCode(TARGET)).willReturn(Optional.of(target));
        given(comparisonRepository.findValues(any(), any(), anyInt(), anyInt())).willReturn(List.of());

        IndustryComparisonResponse response = service.compare(TARGET, null, null, 2025);

        assertThat(response.industry().code()).isNull();
        assertThat(response.industry().companyCount()).isZero();
        then(comparisonRepository).should(never()).countByIndustry(anyString());
    }

    @Test
    @DisplayName("year 를 안 주면 기준연도로 조회한다")
    void defaultsYearToBaseYear() {
        CompanyDetailProjection target = target("26", "전자 부품 제조업");
        given(companyRepository.findDetailByCorpCode(TARGET)).willReturn(Optional.of(target));
        given(comparisonRepository.findValues(any(), any(), eq(2025), eq(2024))).willReturn(List.of());

        IndustryComparisonResponse response = service.compare(TARGET, null, null, null);

        assertThat(response.year()).isEqualTo(2025);
        then(comparisonRepository).should().findValues(any(), any(), eq(2025), eq(2024));
    }

    @Test
    @DisplayName("기준연도에 적재된 값이 없어도 그 해로 조회하고 지표만 전부 null 이다")
    void emptyDefaultYearStillQueriesThatYear() {
        CompanyDetailProjection target = target("26", "전자 부품 제조업");
        given(companyRepository.findDetailByCorpCode(TARGET)).willReturn(Optional.of(target));
        given(comparisonRepository.findValues(any(), any(), anyInt(), anyInt())).willReturn(List.of());

        IndustryComparisonResponse response = service.compare(TARGET, null, null, null);

        // 명세가 기본 연도를 2025 로 못박아서, 적재가 없어도 year 는 null 이 되지 않는다.
        assertThat(response.year()).isEqualTo(2025);
        assertThat(response.companies()).hasSize(1);
        assertThat(response.companies().getFirst().isTarget()).isTrue();
        assertThat(response.companies().getFirst().values().get("revenue")).isNull();
    }

    @Test
    @DisplayName("peers 가 없어도 대상 기업은 값이 없어도 담아 반환한다")
    void alwaysIncludesTarget() {
        CompanyDetailProjection target = target("26", "전자 부품 제조업");
        given(companyRepository.findDetailByCorpCode(TARGET)).willReturn(Optional.of(target));
        given(comparisonRepository.findValues(any(), any(), anyInt(), anyInt())).willReturn(List.of());

        IndustryComparisonResponse response = service.compare(TARGET, null, null, 2025);

        assertThat(response.companies()).hasSize(1);
        assertThat(response.companies().getFirst().corpCode()).isEqualTo(TARGET);
        assertThat(response.companies().getFirst().isTarget()).isTrue();
        assertThat(response.companies().getFirst().values().get("revenue")).isNull();
    }

    @Test
    @DisplayName("없는 기업은 COMPANY_NOT_FOUND 로 예외를 던진다")
    void unknownCompanyThrows() {
        given(companyRepository.findDetailByCorpCode("00000000")).willReturn(Optional.empty());

        assertThatThrownBy(() -> service.compare("00000000", null, null, 2025))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.COMPANY_NOT_FOUND);
    }

    /** dataYear 는 스텁하지 않는다. v2 는 기준연도를 적재 전체에서 정하므로 이 기업 값을 읽지 않는다. */
    private CompanyDetailProjection target(String industryCode, String industryName) {
        CompanyDetailProjection projection = mock(CompanyDetailProjection.class);
        given(projection.getCorpCode()).willReturn(TARGET);
        given(projection.getCorpName()).willReturn("SK하이닉스");
        given(projection.getIndustryCode()).willReturn(industryCode);
        given(projection.getIndustryName()).willReturn(industryName);
        return projection;
    }

    private IndustryComparisonProjection row(String corpCode, String corpName, String metricCode,
                                             Integer fiscalYear, BigDecimal value, Short valueScale) {
        IndustryComparisonProjection projection = mock(IndustryComparisonProjection.class);
        given(projection.getCorpCode()).willReturn(corpCode);
        given(projection.getCorpName()).willReturn(corpName);
        given(projection.getMetricCode()).willReturn(metricCode);
        given(projection.getFiscalYear()).willReturn(fiscalYear);
        given(projection.getValue()).willReturn(value);
        given(projection.getValueScale()).willReturn(valueScale);
        return projection;
    }
}

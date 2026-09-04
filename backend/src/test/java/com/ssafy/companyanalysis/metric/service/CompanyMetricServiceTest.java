package com.ssafy.companyanalysis.metric.service;

import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.global.year.BaseYearResolver;
import com.ssafy.companyanalysis.metric.domain.Metric;
import com.ssafy.companyanalysis.metric.dto.CompanyMetricsResponse;
import com.ssafy.companyanalysis.metric.dto.MetricPointResponse;
import com.ssafy.companyanalysis.metric.dto.MetricRangeResponse;
import com.ssafy.companyanalysis.metric.dto.MetricTimeseriesResponse;
import com.ssafy.companyanalysis.metric.dto.MetricValueResponse;
import com.ssafy.companyanalysis.metric.dto.ProfitabilityResponse;
import com.ssafy.companyanalysis.metric.repository.MetricAmountProjection;
import com.ssafy.companyanalysis.metric.repository.MetricPointProjection;
import com.ssafy.companyanalysis.metric.repository.MetricRepository;
import com.ssafy.companyanalysis.metric.repository.MetricValueProjection;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyCollection;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

/**
 * 값 자릿수·증감률·비율·null 규칙처럼 DB 없이 확정할 수 있는 부분을 검증한다.
 * 실제 쿼리는 DB 가 있어야 하므로 F-36 통합 테스트에서 다룬다.
 */
class CompanyMetricServiceTest {

    private static final String CORP_CODE = "00164779";

    /** 기준연도 계산은 BaseYearResolverTest 가 맡는다. 여기서는 고정값을 준다. */
    private static final int BASE_YEAR = 2025;

    private CompanyRepository companyRepository;
    private MetricRepository metricRepository;
    private BaseYearResolver baseYearResolver;
    private CompanyMetricService service;

    @BeforeEach
    void setUp() {
        companyRepository = mock(CompanyRepository.class);
        metricRepository = mock(MetricRepository.class);
        baseYearResolver = mock(BaseYearResolver.class);
        given(baseYearResolver.resolve()).willReturn(BASE_YEAR);
        service = new CompanyMetricService(companyRepository, metricRepository, baseYearResolver);

        given(companyRepository.existsById(CORP_CODE)).willReturn(true);
    }

    @Test
    @DisplayName("전년 값이 있으면 증감률을 소수 1자리로 계산한다")
    void calculatesChangeRate() {
        givenCatalog(core("revenue", "매출액", "KRW"));
        givenLatestYear(2025);
        given(metricRepository.findMetricValues(CORP_CODE, List.of("revenue"), 2025, 2024))
                .willReturn(List.of(projection("revenue", "매출액", "KRW", 0,
                        bd("71000000000000"), bd("66193000000000"))));

        MetricValueResponse revenue = service.getMetrics(CORP_CODE, null, null).metrics().getFirst();

        assertThat(revenue.yoy().changeRate()).isEqualByComparingTo("7.3");
        assertThat(revenue.yoy().prevValue()).isEqualByComparingTo("66193000000000");
    }

    @Test
    @DisplayName("금액은 카탈로그의 value_scale 대로 소수점을 떨어낸다")
    void appliesValueScale() {
        givenCatalog(core("revenue", "매출액", "KRW"), core("average_tenure", "평균 근속", "YEAR"));
        givenLatestYear(2025);
        given(metricRepository.findMetricValues(CORP_CODE, List.of("revenue", "average_tenure"), 2025, 2024))
                .willReturn(List.of(
                        projection("revenue", "매출액", "KRW", 0, bd("71000000000000.0000"), null),
                        projection("average_tenure", "평균 근속", "YEAR", 1, bd("11.5000"), null)));

        List<MetricValueResponse> metrics = service.getMetrics(CORP_CODE, null, null).metrics();

        assertThat(metrics.get(0).value().toPlainString()).isEqualTo("71000000000000");
        assertThat(metrics.get(1).value().toPlainString()).isEqualTo("11.5");
    }

    @Test
    @DisplayName("값이 없어도 지표 자리는 유지되고 value 는 0 이 아니라 null 이다")
    void keepsShapeWhenValueMissing() {
        givenCatalog(core("net_income", "당기순이익", "KRW"));
        givenLatestYear(2025);
        given(metricRepository.findMetricValues(CORP_CODE, List.of("net_income"), 2025, 2024))
                .willReturn(List.of(projection("net_income", "당기순이익", "KRW", 0, null, null)));

        MetricValueResponse netIncome = service.getMetrics(CORP_CODE, null, null).metrics().getFirst();

        assertThat(netIncome.key()).isEqualTo("net_income");
        assertThat(netIncome.unit()).isEqualTo("KRW");
        assertThat(netIncome.value()).isNull();
        assertThat(netIncome.yoy()).isNull();
    }

    @Test
    @DisplayName("전년 값이 0 이면 증감률은 null 이지만 prevValue 는 그대로 내보낸다")
    void doesNotDivideByZero() {
        givenCatalog(core("operating_profit", "영업이익", "KRW"));
        givenLatestYear(2025);
        given(metricRepository.findMetricValues(CORP_CODE, List.of("operating_profit"), 2025, 2024))
                .willReturn(List.of(projection("operating_profit", "영업이익", "KRW", 0,
                        bd("1000"), BigDecimal.ZERO)));

        MetricValueResponse profit = service.getMetrics(CORP_CODE, null, null).metrics().getFirst();

        assertThat(profit.yoy().prevValue()).isEqualByComparingTo("0");
        assertThat(profit.yoy().changeRate()).isNull();
    }

    @Test
    @DisplayName("전년이 적자(음수)면 부호가 뒤집힌 증감률을 만들지 않는다")
    void doesNotComputeRateFromNegativeBase() {
        givenCatalog(core("operating_profit", "영업이익", "KRW"));
        givenLatestYear(2025);
        given(metricRepository.findMetricValues(CORP_CODE, List.of("operating_profit"), 2025, 2024))
                .willReturn(List.of(projection("operating_profit", "영업이익", "KRW", 0,
                        bd("1000"), bd("-500"))));

        MetricValueResponse profit = service.getMetrics(CORP_CODE, null, null).metrics().getFirst();

        assertThat(profit.yoy().prevValue()).isEqualByComparingTo("-500");
        assertThat(profit.yoy().changeRate()).isNull();
    }

    @Test
    @DisplayName("keys 를 주면 기본 6종 대신 그 지표만 조회한다")
    void queriesOnlyRequestedKeysInSingleYear() {
        givenCatalog(core("revenue", "매출액", "KRW"), core("net_income", "당기순이익", "KRW"));
        given(metricRepository.findMetricValues(CORP_CODE, List.of("net_income"), 2025, 2024))
                .willReturn(List.of(projection("net_income", "당기순이익", "KRW", 0, bd("100"), null)));

        List<MetricValueResponse> metrics =
                service.getMetrics(CORP_CODE, 2025, List.of("net_income")).metrics();

        assertThat(metrics).hasSize(1);
        assertThat(metrics.getFirst().key()).isEqualTo("net_income");
    }

    @Test
    @DisplayName("기본 6종에서 빠진 지표도 keys 로는 요청할 수 있다")
    void allowsRequestingNonCoreMetric() {
        // 산업 비교 화면이 rd_ratio 를 keys 로 직접 요청한다. 기본에서 빠졌다고 400 이 되면 그 화면이 깨진다.
        givenCatalog(core("revenue", "매출액", "KRW"), nonCore("rd_ratio", "R&D/매출", "%"));
        given(metricRepository.findMetricValues(CORP_CODE, List.of("rd_ratio"), 2025, 2024))
                .willReturn(List.of(projection("rd_ratio", "R&D/매출", "%", 1, bd("8.1000"), null)));

        List<MetricValueResponse> metrics =
                service.getMetrics(CORP_CODE, 2025, List.of("rd_ratio")).metrics();

        assertThat(metrics).hasSize(1);
        assertThat(metrics.getFirst().key()).isEqualTo("rd_ratio");
    }

    @Test
    @DisplayName("keys 가 없으면 기본 6종만 나가고 core 가 아닌 지표는 빠진다")
    void defaultsToCoreMetrics() {
        givenCatalog(core("revenue", "매출액", "KRW"), nonCore("rd_ratio", "R&D/매출", "%"));
        given(metricRepository.findMetricValues(CORP_CODE, List.of("revenue"), 2025, 2024))
                .willReturn(List.of(projection("revenue", "매출액", "KRW", 0, bd("100"), null)));

        List<MetricValueResponse> metrics = service.getMetrics(CORP_CODE, 2025, null).metrics();

        assertThat(metrics).extracting(MetricValueResponse::key).containsExactly("revenue");
    }

    @Test
    @DisplayName("수익성·안정성 비율을 백분율 소수 1자리로 계산한다")
    void calculatesProfitability() {
        givenCatalog(core("revenue", "매출액", "KRW"));
        givenRawValues(2025,
                raw("revenue", bd("1000")),
                raw("operating_profit", bd("124")),
                raw("net_income", bd("83")),
                raw("total_liabilities", bd("427")),
                raw("total_equity", bd("1000")));

        ProfitabilityResponse profitability = service.getMetrics(CORP_CODE, 2025, null).profitability();

        assertThat(profitability.operatingMargin()).isEqualByComparingTo("12.4");
        assertThat(profitability.netMargin()).isEqualByComparingTo("8.3");
        assertThat(profitability.debtRatio()).isEqualByComparingTo("42.7");
    }

    @Test
    @DisplayName("원본이 없는 비율만 null 이고 나머지는 그대로 계산된다")
    void computesAvailableRatiosOnly() {
        givenCatalog(core("revenue", "매출액", "KRW"));
        givenRawValues(2025,
                raw("revenue", bd("1000")),
                raw("operating_profit", bd("124")));

        ProfitabilityResponse profitability = service.getMetrics(CORP_CODE, 2025, null).profitability();

        assertThat(profitability.operatingMargin()).isEqualByComparingTo("12.4");
        assertThat(profitability.netMargin()).isNull();
        assertThat(profitability.debtRatio()).isNull();
    }

    @Test
    @DisplayName("자본잠식(자본총계 0 이하)이면 부채비율을 만들지 않는다")
    void doesNotComputeDebtRatioOnNegativeEquity() {
        givenCatalog(core("revenue", "매출액", "KRW"));
        givenRawValues(2025,
                raw("total_liabilities", bd("500")),
                raw("total_equity", bd("-100")));

        assertThat(service.getMetrics(CORP_CODE, 2025, null).profitability().debtRatio()).isNull();
    }

    @Test
    @DisplayName("원본이 하나도 없어도 profitability 블록 자체는 유지된다")
    void keepsProfitabilityBlockWhenNothingLoaded() {
        givenCatalog(core("revenue", "매출액", "KRW"));

        ProfitabilityResponse profitability = service.getMetrics(CORP_CODE, 2025, null).profitability();

        assertThat(profitability).isNotNull();
        assertThat(profitability.operatingMargin()).isNull();
        assertThat(profitability.netMargin()).isNull();
        assertThat(profitability.debtRatio()).isNull();
    }

    @Test
    @DisplayName("적재된 값이 하나도 없으면 year 는 null 이고 지표 골격만 돌려준다")
    void returnsSkeletonWhenNothingLoaded() {
        givenCatalog(core("revenue", "매출액", "KRW"), core("net_income", "당기순이익", "KRW"));
        given(metricRepository.findLatestFiscalYear(CORP_CODE)).willReturn(null);

        CompanyMetricsResponse response = service.getMetrics(CORP_CODE, null, null);

        assertThat(response.year()).isNull();
        assertThat(response.metrics()).hasSize(2);
        assertThat(response.metrics()).allMatch(metric -> metric.value() == null && metric.yoy() == null);
        assertThat(response.profitability()).isNotNull();
        assertThat(response.profitability().operatingMargin()).isNull();
    }

    @Test
    @DisplayName("없는 기업은 COMPANY_NOT_FOUND")
    void unknownCompanyIsNotFound() {
        given(companyRepository.existsById("00000000")).willReturn(false);

        assertThatThrownBy(() -> service.getMetrics("00000000", null, null))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.COMPANY_NOT_FOUND);
    }

    @Test
    @DisplayName("year 를 주면 최신연도를 조회하지 않고 그 연도를 기준으로 삼는다")
    void usesRequestedYear() {
        givenCatalog(core("revenue", "매출액", "KRW"));
        given(metricRepository.findMetricValues(CORP_CODE, List.of("revenue"), 2021, 2020))
                .willReturn(List.of(projection("revenue", "매출액", "KRW", 0, bd("100"), null)));

        CompanyMetricsResponse response = service.getMetrics(CORP_CODE, 2021, null);

        assertThat(response.year()).isEqualTo(2021);
    }

    @Test
    @DisplayName("시계열은 구간의 모든 연도를 오름차순으로 채우고 빠진 해는 null 이다")
    void fillsMissingYearsWithNull() {
        givenCatalog(core("revenue", "매출액", "KRW"));
        givenPoints(List.of("revenue"),
                point("revenue", "매출액", "KRW", 0, 2021, bd("42998000000000")),
                point("revenue", "매출액", "KRW", 0, 2025, bd("71000000000000")));

        MetricTimeseriesResponse response = service.getTimeseries(CORP_CODE, null, null, null);

        assertThat(response.range()).isEqualTo(new MetricRangeResponse(2021, 2025));
        List<MetricPointResponse> points = response.series().getFirst().points();
        assertThat(points).extracting(MetricPointResponse::year).containsExactly(2021, 2022, 2023, 2024, 2025);
        assertThat(points.get(0).value()).isEqualByComparingTo("42998000000000");
        assertThat(points.get(1).value()).isNull();
        assertThat(points.get(2).value()).isNull();
        assertThat(points.get(3).value()).isNull();
        assertThat(points.get(4).value()).isEqualByComparingTo("71000000000000");
    }

    @Test
    @DisplayName("구간 첫 해의 증감률도 전년 값을 읽어와 채운다")
    void fillsChangeRateOfFirstYear() {
        givenCatalog(core("revenue", "매출액", "KRW"));
        givenPoints(List.of("revenue"),
                point("revenue", "매출액", "KRW", 0, 2020, bd("1000")),
                point("revenue", "매출액", "KRW", 0, 2021, bd("1073")));

        List<MetricPointResponse> points =
                service.getTimeseries(CORP_CODE, null, null, null).series().getFirst().points();

        // 2020 은 요청 구간 밖이라 격자에 들어가지 않는다.
        assertThat(points).extracting(MetricPointResponse::year).containsExactly(2021, 2022, 2023, 2024, 2025);
        assertThat(points.getFirst().changeRate()).isEqualByComparingTo("7.3");
    }

    @Test
    @DisplayName("전년 값이 없는 해는 값이 있어도 증감률이 null 이다")
    void leavesChangeRateNullWithoutPreviousYear() {
        givenCatalog(core("revenue", "매출액", "KRW"));
        givenPoints(List.of("revenue"), point("revenue", "매출액", "KRW", 0, 2021, bd("1073")));

        List<MetricPointResponse> points =
                service.getTimeseries(CORP_CODE, null, null, null).series().getFirst().points();

        assertThat(points.getFirst().value()).isEqualByComparingTo("1073");
        assertThat(points.getFirst().changeRate()).isNull();
    }

    @Test
    @DisplayName("구간에 값이 하나도 없는 지표도 연도 자리는 모두 채워 내보낸다")
    void keepsYearGridForEmptySeries() {
        givenCatalog(core("net_income", "당기순이익", "KRW"));
        givenPoints(List.of("net_income"), point("net_income", "당기순이익", "KRW", 0, null, null));

        List<MetricPointResponse> points =
                service.getTimeseries(CORP_CODE, null, null, null).series().getFirst().points();

        assertThat(points).hasSize(5);
        assertThat(points).allMatch(p -> p.value() == null && p.changeRate() == null);
    }

    @Test
    @DisplayName("keys 를 주면 그 지표만 조회한다")
    void queriesOnlyRequestedKeys() {
        givenCatalog(core("revenue", "매출액", "KRW"), core("average_tenure", "평균 근속", "YEAR"));
        givenPoints(List.of("average_tenure"),
                point("average_tenure", "평균 근속", "YEAR", 1, 2025, bd("11.5000")));

        MetricTimeseriesResponse response = service.getTimeseries(CORP_CODE, null, null, List.of("average-tenure"));

        assertThat(response.series()).hasSize(1);
        assertThat(response.series().getFirst().key()).isEqualTo("average_tenure");
        assertThat(response.series().getFirst().points().getLast().value().toPlainString()).isEqualTo("11.5");
    }

    @Test
    @DisplayName("keys 에 지원하지 않는 지표가 섞이면 METRIC_NOT_SUPPORTED")
    void rejectsUnsupportedKeys() {
        givenCatalog(core("revenue", "매출액", "KRW"));

        assertThatThrownBy(() -> service.getTimeseries(CORP_CODE, null, null, List.of("revenue", "market_cap")))
                .isInstanceOf(BusinessException.class)
                .hasMessageContaining("market_cap")
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.METRIC_NOT_SUPPORTED);
    }

    @Test
    @DisplayName("from 이 to 보다 크면 INVALID_PARAMETER")
    void rejectsInvertedRange() {
        assertThatThrownBy(() -> service.getTimeseries(CORP_CODE, 2025, 2021, null))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.INVALID_PARAMETER);
    }

    @Test
    @DisplayName("시계열도 없는 기업이면 COMPANY_NOT_FOUND")
    void timeseriesOfUnknownCompanyIsNotFound() {
        given(companyRepository.existsById("00000000")).willReturn(false);

        assertThatThrownBy(() -> service.getTimeseries("00000000", null, null, null))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.COMPANY_NOT_FOUND);
    }

    private void givenCatalog(Metric... metrics) {
        given(metricRepository.findByActiveTrueOrderByDisplayOrderAsc()).willReturn(List.of(metrics));
    }

    /** 기본 구간(기준연도 포함 5년)의 시계열. 서비스가 첫 해 증감률 때문에 한 해 앞에서 읽는 것까지 함께 고정한다. */
    private void givenPoints(List<String> metricCodes, MetricPointProjection... rows) {
        given(metricRepository.findMetricPoints(CORP_CODE, metricCodes, 2020, 2025)).willReturn(List.of(rows));
    }

    private void givenRawValues(int year, MetricAmountProjection... rows) {
        given(metricRepository.findRawValues(eq(CORP_CODE), anyCollection(), eq(year))).willReturn(List.of(rows));
    }

    private void givenLatestYear(int year) {
        given(metricRepository.findLatestFiscalYear(CORP_CODE)).willReturn(year);
    }

    private static BigDecimal bd(String value) {
        return new BigDecimal(value);
    }

    /** 엔티티는 생성자가 막혀 있어, 조회 결과 대역만 필요한 곳에서는 목으로 만든다. */
    private static Metric core(String metricCode, String nameKo, String unit) {
        return catalog(metricCode, nameKo, unit, true);
    }

    /** 요청은 가능하지만 기본 6종에는 들어가지 않는 지표(rd_ratio 등). */
    private static Metric nonCore(String metricCode, String nameKo, String unit) {
        return catalog(metricCode, nameKo, unit, false);
    }

    private static Metric catalog(String metricCode, String nameKo, String unit, boolean core) {
        Metric metric = mock(Metric.class);
        given(metric.getMetricCode()).willReturn(metricCode);
        given(metric.getNameKo()).willReturn(nameKo);
        given(metric.getUnit()).willReturn(unit);
        given(metric.isCore()).willReturn(core);
        return metric;
    }

    private static MetricValueProjection projection(String metricCode, String label, String unit,
                                                    int valueScale, BigDecimal value, BigDecimal prevValue) {
        return new StubProjection(metricCode, label, unit, (short) valueScale, value, prevValue);
    }

    /** fiscalYear 가 null 이면 그 지표는 구간 안에 값이 하나도 없다는 뜻이다. */
    private static MetricPointProjection point(String metricCode, String label, String unit,
                                               int valueScale, Integer fiscalYear, BigDecimal value) {
        return new StubPointProjection(metricCode, label, unit, (short) valueScale, fiscalYear, value);
    }

    private static MetricAmountProjection raw(String metricCode, BigDecimal value) {
        return new StubAmountProjection(metricCode, value);
    }

    private record StubProjection(String metricCode, String label, String unit, short valueScale,
                                  BigDecimal value, BigDecimal prevValue) implements MetricValueProjection {

        @Override
        public String getMetricCode() {
            return metricCode;
        }

        @Override
        public String getLabel() {
            return label;
        }

        @Override
        public String getUnit() {
            return unit;
        }

        @Override
        public short getValueScale() {
            return valueScale;
        }

        @Override
        public BigDecimal getValue() {
            return value;
        }

        @Override
        public BigDecimal getPrevValue() {
            return prevValue;
        }
    }

    private record StubPointProjection(String metricCode, String label, String unit, short valueScale,
                                       Integer fiscalYear, BigDecimal value) implements MetricPointProjection {

        @Override
        public String getMetricCode() {
            return metricCode;
        }

        @Override
        public String getLabel() {
            return label;
        }

        @Override
        public String getUnit() {
            return unit;
        }

        @Override
        public short getValueScale() {
            return valueScale;
        }

        @Override
        public Integer getFiscalYear() {
            return fiscalYear;
        }

        @Override
        public BigDecimal getValue() {
            return value;
        }
    }

    private record StubAmountProjection(String metricCode, BigDecimal value) implements MetricAmountProjection {

        @Override
        public String getMetricCode() {
            return metricCode;
        }

        @Override
        public BigDecimal getValue() {
            return value;
        }
    }
}

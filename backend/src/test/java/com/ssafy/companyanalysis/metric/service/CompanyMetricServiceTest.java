package com.ssafy.companyanalysis.metric.service;

import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.metric.domain.Metric;
import com.ssafy.companyanalysis.metric.dto.CompanyMetricsResponse;
import com.ssafy.companyanalysis.metric.dto.MetricPointResponse;
import com.ssafy.companyanalysis.metric.dto.MetricRangeResponse;
import com.ssafy.companyanalysis.metric.dto.MetricTimeseriesResponse;
import com.ssafy.companyanalysis.metric.dto.MetricValueResponse;
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
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

/**
 * 값 자릿수·증감률·null 규칙처럼 DB 없이 확정할 수 있는 부분을 검증한다.
 * 실제 쿼리는 DB 가 있어야 하므로 F-36 통합 테스트에서 다룬다.
 */
class CompanyMetricServiceTest {

    private static final String CORP_CODE = "00164779";

    private CompanyRepository companyRepository;
    private MetricRepository metricRepository;
    private CompanyMetricService service;

    @BeforeEach
    void setUp() {
        companyRepository = mock(CompanyRepository.class);
        metricRepository = mock(MetricRepository.class);
        service = new CompanyMetricService(companyRepository, metricRepository);

        given(companyRepository.existsById(CORP_CODE)).willReturn(true);
    }

    @Test
    @DisplayName("전년 값이 있으면 증감률을 소수 1자리로 계산한다")
    void calculatesChangeRate() {
        givenLatestYear(2025);
        given(metricRepository.findMetricValues(CORP_CODE, 2025, 2024))
                .willReturn(List.of(projection("revenue", "매출액", "KRW", 0,
                        bd("71000000000000"), bd("66193000000000"))));

        MetricValueResponse revenue = service.getMetrics(CORP_CODE, null, true).metrics().getFirst();

        assertThat(revenue.yoy().changeRate()).isEqualByComparingTo("7.3");
        assertThat(revenue.yoy().prevValue()).isEqualByComparingTo("66193000000000");
    }

    @Test
    @DisplayName("금액은 카탈로그의 value_scale 대로 소수점을 떨어낸다")
    void appliesValueScale() {
        givenLatestYear(2025);
        given(metricRepository.findMetricValues(CORP_CODE, 2025, 2024))
                .willReturn(List.of(
                        projection("revenue", "매출액", "KRW", 0, bd("71000000000000.0000"), null),
                        projection("average_tenure", "평균 근속", "YEAR", 1, bd("11.5000"), null)));

        List<MetricValueResponse> metrics = service.getMetrics(CORP_CODE, null, true).metrics();

        assertThat(metrics.get(0).value().toPlainString()).isEqualTo("71000000000000");
        assertThat(metrics.get(1).value().toPlainString()).isEqualTo("11.5");
    }

    @Test
    @DisplayName("값이 없어도 지표 자리는 유지되고 value 는 0 이 아니라 null 이다")
    void keepsShapeWhenValueMissing() {
        givenLatestYear(2025);
        given(metricRepository.findMetricValues(CORP_CODE, 2025, 2024))
                .willReturn(List.of(projection("rd_ratio", "R&D/매출", "%", 1, null, null)));

        MetricValueResponse rdRatio = service.getMetrics(CORP_CODE, null, true).metrics().getFirst();

        assertThat(rdRatio.key()).isEqualTo("rd_ratio");
        assertThat(rdRatio.unit()).isEqualTo("%");
        assertThat(rdRatio.value()).isNull();
        assertThat(rdRatio.yoy()).isNull();
    }

    @Test
    @DisplayName("전년 값이 0 이면 증감률은 null 이지만 prevValue 는 그대로 내보낸다")
    void doesNotDivideByZero() {
        givenLatestYear(2025);
        given(metricRepository.findMetricValues(CORP_CODE, 2025, 2024))
                .willReturn(List.of(projection("operating_profit", "영업이익", "KRW", 0,
                        bd("1000"), BigDecimal.ZERO)));

        MetricValueResponse profit = service.getMetrics(CORP_CODE, null, true).metrics().getFirst();

        assertThat(profit.yoy().prevValue()).isEqualByComparingTo("0");
        assertThat(profit.yoy().changeRate()).isNull();
    }

    @Test
    @DisplayName("전년이 적자(음수)면 부호가 뒤집힌 증감률을 만들지 않는다")
    void doesNotComputeRateFromNegativeBase() {
        givenLatestYear(2025);
        given(metricRepository.findMetricValues(CORP_CODE, 2025, 2024))
                .willReturn(List.of(projection("operating_profit", "영업이익", "KRW", 0,
                        bd("1000"), bd("-500"))));

        MetricValueResponse profit = service.getMetrics(CORP_CODE, null, true).metrics().getFirst();

        assertThat(profit.yoy().prevValue()).isEqualByComparingTo("-500");
        assertThat(profit.yoy().changeRate()).isNull();
    }

    @Test
    @DisplayName("yoy=false 면 전년 대비를 붙이지 않는다")
    void omitsYoyWhenNotRequested() {
        given(metricRepository.findMetricValues(CORP_CODE, 2025, 2024))
                .willReturn(List.of(projection("revenue", "매출액", "KRW", 0,
                        bd("71000000000000"), bd("66193000000000"))));

        MetricValueResponse revenue = service.getMetrics(CORP_CODE, 2025, false).metrics().getFirst();

        assertThat(revenue.value()).isNotNull();
        assertThat(revenue.yoy()).isNull();
    }

    @Test
    @DisplayName("적재된 값이 하나도 없으면 year 는 null 이고 지표 골격만 돌려준다")
    void returnsSkeletonWhenNothingLoaded() {
        // 목을 만드는 것도 스터빙이라 바깥 given(...) 안에서 만들면 스터빙이 겹친다.
        List<Metric> catalog = List.of(catalog("revenue", "매출액", "KRW"), catalog("rd_ratio", "R&D/매출", "%"));
        given(metricRepository.findLatestFiscalYear(CORP_CODE)).willReturn(null);
        given(metricRepository.findByActiveTrueOrderByDisplayOrderAsc()).willReturn(catalog);

        CompanyMetricsResponse response = service.getMetrics(CORP_CODE, null, true);

        assertThat(response.year()).isNull();
        assertThat(response.metrics()).hasSize(2);
        assertThat(response.metrics()).allMatch(metric -> metric.value() == null && metric.yoy() == null);
    }

    @Test
    @DisplayName("없는 기업은 COMPANY_NOT_FOUND")
    void unknownCompanyIsNotFound() {
        given(companyRepository.existsById("00000000")).willReturn(false);

        assertThatThrownBy(() -> service.getMetrics("00000000", null, true))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.COMPANY_NOT_FOUND);
    }

    @Test
    @DisplayName("year 를 주면 최신연도를 조회하지 않고 그 연도를 기준으로 삼는다")
    void usesRequestedYear() {
        given(metricRepository.findMetricValues(CORP_CODE, 2021, 2020))
                .willReturn(List.of(projection("revenue", "매출액", "KRW", 0, bd("100"), null)));

        CompanyMetricsResponse response = service.getMetrics(CORP_CODE, 2021, true);

        assertThat(response.year()).isEqualTo(2021);
    }

    @Test
    @DisplayName("시계열은 구간의 모든 연도를 오름차순으로 채우고 빠진 해는 null 이다")
    void fillsMissingYearsWithNull() {
        givenActiveCatalog(catalog("revenue", "매출액", "KRW"));
        given(metricRepository.findMetricPoints(CORP_CODE, List.of("revenue"), 2021, 2025))
                .willReturn(List.of(
                        point("revenue", "매출액", "KRW", 0, 2021, bd("42998000000000")),
                        point("revenue", "매출액", "KRW", 0, 2025, bd("71000000000000"))));

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
    @DisplayName("구간에 값이 하나도 없는 지표도 연도 자리는 모두 채워 내보낸다")
    void keepsYearGridForEmptySeries() {
        givenActiveCatalog(catalog("rd_ratio", "R&D/매출", "%"));
        given(metricRepository.findMetricPoints(CORP_CODE, List.of("rd_ratio"), 2021, 2025))
                .willReturn(List.of(point("rd_ratio", "R&D/매출", "%", 1, null, null)));

        List<MetricPointResponse> points =
                service.getTimeseries(CORP_CODE, null, null, null).series().getFirst().points();

        assertThat(points).hasSize(5);
        assertThat(points).allMatch(p -> p.value() == null);
    }

    @Test
    @DisplayName("keys 를 주면 그 지표만 조회한다")
    void queriesOnlyRequestedKeys() {
        givenActiveCatalog(catalog("revenue", "매출액", "KRW"), catalog("average_tenure", "평균 근속", "YEAR"));
        given(metricRepository.findMetricPoints(CORP_CODE, List.of("average_tenure"), 2021, 2025))
                .willReturn(List.of(point("average_tenure", "평균 근속", "YEAR", 1, 2025, bd("11.5000"))));

        MetricTimeseriesResponse response = service.getTimeseries(CORP_CODE, null, null, List.of("average-tenure"));

        assertThat(response.series()).hasSize(1);
        assertThat(response.series().getFirst().key()).isEqualTo("average_tenure");
        assertThat(response.series().getFirst().points().getLast().value().toPlainString()).isEqualTo("11.5");
    }

    @Test
    @DisplayName("keys 에 지원하지 않는 지표가 섞이면 METRIC_NOT_SUPPORTED")
    void rejectsUnsupportedKeys() {
        givenActiveCatalog(catalog("revenue", "매출액", "KRW"));

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

    private void givenActiveCatalog(Metric... metrics) {
        List<Metric> catalog = List.of(metrics);
        given(metricRepository.findByActiveTrueOrderByDisplayOrderAsc()).willReturn(catalog);
    }

    private void givenLatestYear(int year) {
        given(metricRepository.findLatestFiscalYear(CORP_CODE)).willReturn(year);
    }

    private static BigDecimal bd(String value) {
        return new BigDecimal(value);
    }

    /** 엔티티는 생성자가 막혀 있어, 조회 결과 대역만 필요한 곳에서는 목으로 만든다. */
    private static Metric catalog(String metricCode, String nameKo, String unit) {
        Metric metric = mock(Metric.class);
        given(metric.getMetricCode()).willReturn(metricCode);
        given(metric.getNameKo()).willReturn(nameKo);
        given(metric.getUnit()).willReturn(unit);
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
}

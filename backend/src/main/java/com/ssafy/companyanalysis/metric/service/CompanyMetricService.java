package com.ssafy.companyanalysis.metric.service;

import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.metric.domain.Metric;
import com.ssafy.companyanalysis.metric.dto.CompanyMetricsResponse;
import com.ssafy.companyanalysis.metric.dto.MetricPointResponse;
import com.ssafy.companyanalysis.metric.dto.MetricRangeResponse;
import com.ssafy.companyanalysis.metric.dto.MetricSeriesResponse;
import com.ssafy.companyanalysis.metric.dto.MetricTimeseriesResponse;
import com.ssafy.companyanalysis.metric.dto.MetricValueResponse;
import com.ssafy.companyanalysis.metric.dto.ProfitabilityResponse;
import com.ssafy.companyanalysis.metric.dto.YoyResponse;
import com.ssafy.companyanalysis.metric.repository.MetricAmountProjection;
import com.ssafy.companyanalysis.metric.repository.MetricPointProjection;
import com.ssafy.companyanalysis.metric.repository.MetricRepository;
import com.ssafy.companyanalysis.metric.repository.MetricValueProjection;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.IntStream;

@Service
public class CompanyMetricService {

    private static final BigDecimal HUNDRED = BigDecimal.valueOf(100);

    /** 증감률·비율 소수 자릿수. 명세 예시가 7.3 이라 1자리로 고정한다. */
    private static final int RATE_SCALE = 1;

    /** 명세가 정한 시계열 기본 구간. MVP 의 관심 구간이 2021~2025 다. */
    private static final int DEFAULT_FROM_YEAR = 2021;
    private static final int DEFAULT_TO_YEAR = 2025;

    /** 수익성·안정성 비율의 원본 지표. 앞의 셋은 기본 6종이고 뒤의 둘은 내부 지표다(V7). */
    private static final String REVENUE = "revenue";
    private static final String OPERATING_PROFIT = "operating_profit";
    private static final String NET_INCOME = "net_income";
    private static final String TOTAL_LIABILITIES = "total_liabilities";
    private static final String TOTAL_EQUITY = "total_equity";

    private static final List<String> PROFITABILITY_SOURCES =
            List.of(REVENUE, OPERATING_PROFIT, NET_INCOME, TOTAL_LIABILITIES, TOTAL_EQUITY);

    /** 계산할 원본이 하나도 없을 때 내보내는 빈 블록. 필드를 생략하지 않는다. */
    private static final ProfitabilityResponse EMPTY_PROFITABILITY =
            new ProfitabilityResponse(null, null, null);

    private final CompanyRepository companyRepository;
    private final MetricRepository metricRepository;

    public CompanyMetricService(CompanyRepository companyRepository, MetricRepository metricRepository) {
        this.companyRepository = companyRepository;
        this.metricRepository = metricRepository;
    }

    /**
     * 한 기업의 지정 연도 지표를 수익성·안정성 비율과 함께 조회한다.
     *
     * <p>v2 에서 {@code yoy} 파라미터가 사라졌다. 전년 대비를 끄고 싶다는 요구가 실제로
     * 없었고, 켜고 끌 수 있으면 FE 가 "안 켰다"와 "전년 값이 없다"를 구분해야 해서다.
     * 이제 항상 계산하고, 전년 값이 없을 때만 null 이 된다.
     *
     * @param year null 이면 그 기업의 최신 적재 연도
     * @param keys 조회할 지표 슬러그 목록. 비어 있으면 기본 6종
     */
    @Transactional(readOnly = true)
    public CompanyMetricsResponse getMetrics(String corpCode, Integer year, List<String> keys) {
        requireCompany(corpCode);

        List<Metric> catalog = resolveMetrics(keys);
        Integer targetYear = resolveYear(corpCode, year);
        if (targetYear == null) {
            // 이 기업의 적재값이 하나도 없다. 조회할 연도가 없을 뿐 오류는 아니므로
            // 카탈로그만으로 골격을 만들어 준다.
            return new CompanyMetricsResponse(corpCode, null, emptyMetrics(catalog), EMPTY_PROFITABILITY);
        }

        List<String> metricCodes = toCodes(catalog);
        List<MetricValueResponse> metrics =
                metricRepository.findMetricValues(corpCode, metricCodes, targetYear, targetYear - 1).stream()
                        .map(this::toMetricValue)
                        .toList();

        return new CompanyMetricsResponse(corpCode, targetYear, metrics, profitability(corpCode, targetYear));
    }

    /**
     * 지정 구간의 지표별 시계열을 조회한다(F-14).
     *
     * @param keys 조회할 지표 슬러그 목록. 비어 있으면 기본 6종
     */
    @Transactional(readOnly = true)
    public MetricTimeseriesResponse getTimeseries(String corpCode, Integer from, Integer to, List<String> keys) {
        requireCompany(corpCode);

        MetricRangeResponse range = resolveRange(from, to);
        List<String> metricCodes = toCodes(resolveMetrics(keys));

        // 구간 첫 해의 changeRate 를 내려면 그 전년 값이 필요하다. 한 해 앞에서 조회하고
        // 격자를 만들 때 버린다.
        List<MetricPointProjection> rows =
                metricRepository.findMetricPoints(corpCode, metricCodes, range.from() - 1, range.to());

        return new MetricTimeseriesResponse(range, toSeries(rows, range));
    }

    /**
     * 지표 슬러그를 카탈로그 행으로 바꾼다.
     *
     * <p>비어 있으면 기본 6종({@code is_core})이다. 값이 있으면 요청 가능 범위
     * ({@code is_active})에 있는지 검증한다. 두 범위가 다른 이유는 {@link Metric} 참고.
     *
     * <p>하나라도 카탈로그에 없으면 400 이다. 조용히 걸러내면 FE 는 오타를
     * "데이터가 없는 지표"로 오해하게 된다.
     *
     * <p>반환 순서는 요청한 keys 순서가 아니라 display_order 다. 단년 조회와 시계열이
     * 같은 순서로 나가야 FE 가 같은 색·같은 자리에 그릴 수 있다.
     */
    private List<Metric> resolveMetrics(List<String> keys) {
        List<Metric> supported = metricRepository.findByActiveTrueOrderByDisplayOrderAsc();

        List<String> requested = keys == null ? List.of() : keys.stream()
                .filter(key -> key != null && !key.isBlank())
                .map(this::normalize)
                .distinct()
                .toList();

        if (requested.isEmpty()) {
            return supported.stream().filter(Metric::isCore).toList();
        }

        Set<String> supportedCodes = supported.stream().map(Metric::getMetricCode).collect(Collectors.toSet());
        List<String> unsupported = requested.stream().filter(key -> !supportedCodes.contains(key)).toList();
        if (!unsupported.isEmpty()) {
            throw new BusinessException(ErrorCode.METRIC_NOT_SUPPORTED,
                    "지원하지 않는 지표입니다: " + String.join(", ", unsupported));
        }

        Set<String> wanted = Set.copyOf(requested);
        return supported.stream().filter(metric -> wanted.contains(metric.getMetricCode())).toList();
    }

    /**
     * 지표 슬러그를 DB 의 metric_code 표기로 맞춘다.
     *
     * <p>v1 명세가 같은 지표를 {@code rd_ratio}(snake_case)와 {@code rd-ratio}(kebab-case)
     * 두 표기로 적어 두어, 어느 쪽으로 호출해도 같은 지표를 가리키게 한다.
     * 응답의 {@code key} 는 DB 표기로 통일한다.
     */
    private String normalize(String metric) {
        return metric.trim().toLowerCase().replace('-', '_');
    }

    private static List<String> toCodes(List<Metric> catalog) {
        return catalog.stream().map(Metric::getMetricCode).toList();
    }

    private void requireCompany(String corpCode) {
        if (!companyRepository.existsById(corpCode)) {
            throw new BusinessException(ErrorCode.COMPANY_NOT_FOUND);
        }
    }

    /** 요청 연도가 있으면 그대로, 없으면 최신 적재 연도. 둘 다 없으면 null. */
    private Integer resolveYear(String corpCode, Integer year) {
        return year != null ? year : metricRepository.findLatestFiscalYear(corpCode);
    }

    private MetricRangeResponse resolveRange(Integer from, Integer to) {
        int fromYear = from != null ? from : DEFAULT_FROM_YEAR;
        int toYear = to != null ? to : DEFAULT_TO_YEAR;

        if (fromYear > toYear) {
            throw new BusinessException(ErrorCode.INVALID_PARAMETER, "from 은 to 보다 클 수 없습니다.");
        }
        return new MetricRangeResponse(fromYear, toYear);
    }

    private List<MetricValueResponse> emptyMetrics(List<Metric> catalog) {
        return catalog.stream()
                .map(metric -> new MetricValueResponse(
                        metric.getMetricCode(), metric.getNameKo(), null, metric.getUnit(), null))
                .toList();
    }

    /**
     * 수익성·안정성 비율을 만든다.
     *
     * <p>원본은 {@code keys} 와 무관하게 늘 같은 다섯 개를 읽는다. 사용자가 매출만 골라도
     * 화면의 비율 블록은 그대로 나와야 하기 때문이다.
     */
    private ProfitabilityResponse profitability(String corpCode, int year) {
        Map<String, BigDecimal> raw = metricRepository.findRawValues(corpCode, PROFITABILITY_SOURCES, year).stream()
                .filter(row -> row.getValue() != null)
                .collect(Collectors.toMap(MetricAmountProjection::getMetricCode, MetricAmountProjection::getValue));

        if (raw.isEmpty()) {
            return EMPTY_PROFITABILITY;
        }
        BigDecimal revenue = raw.get(REVENUE);
        return new ProfitabilityResponse(
                ratio(raw.get(OPERATING_PROFIT), revenue),
                ratio(raw.get(NET_INCOME), revenue),
                ratio(raw.get(TOTAL_LIABILITIES), raw.get(TOTAL_EQUITY)));
    }

    /**
     * 백분율을 만든다. 분자가 없거나 분모가 없거나 0 이하면 null 이다.
     *
     * <p>분모가 음수일 때 계산하지 않는 것은 증감률과 같은 이유다. 자본잠식 기업의 부채비율은
     * 부호가 뒤집혀 "부채가 적은 회사"처럼 보인다.
     */
    private BigDecimal ratio(BigDecimal numerator, BigDecimal denominator) {
        if (numerator == null || denominator == null || denominator.signum() <= 0) {
            return null;
        }
        return numerator.multiply(HUNDRED).divide(denominator, RATE_SCALE, RoundingMode.HALF_UP);
    }

    /** 지표별로 묶는다. 쿼리가 display_order 로 정렬해 오므로 순서를 유지하는 맵을 쓴다. */
    private List<MetricSeriesResponse> toSeries(List<MetricPointProjection> rows, MetricRangeResponse range) {
        Map<String, List<MetricPointProjection>> grouped = rows.stream()
                .collect(Collectors.groupingBy(MetricPointProjection::getMetricCode,
                        LinkedHashMap::new, Collectors.toList()));

        return grouped.values().stream()
                .map(group -> toOneSeries(group, range))
                .toList();
    }

    private MetricSeriesResponse toOneSeries(List<MetricPointProjection> group, MetricRangeResponse range) {
        MetricPointProjection head = group.getFirst();
        int scale = head.getValueScale();

        Map<Integer, BigDecimal> valuesByYear = new HashMap<>();
        for (MetricPointProjection row : group) {
            // 구간 안에 값이 하나도 없는 지표는 fiscal_year 가 null 인 행 하나로 온다.
            if (row.getFiscalYear() != null) {
                valuesByYear.put(row.getFiscalYear(), scaled(row.getValue(), scale));
            }
        }

        return new MetricSeriesResponse(head.getMetricCode(), head.getLabel(), head.getUnit(),
                points(valuesByYear, range));
    }

    /**
     * 구간의 모든 연도를 오름차순으로 채운다. 값이 없는 해는 null 이다.
     *
     * <p>{@code from - 1} 은 격자에 넣지 않는다. 첫 해의 증감률을 내기 위해 읽어 왔을 뿐,
     * 요청 구간 밖이라 응답에 실리면 안 된다.
     */
    private List<MetricPointResponse> points(Map<Integer, BigDecimal> valuesByYear, MetricRangeResponse range) {
        return IntStream.rangeClosed(range.from(), range.to())
                .mapToObj(year -> new MetricPointResponse(year, valuesByYear.get(year),
                        changeRate(valuesByYear.get(year), valuesByYear.get(year - 1))))
                .toList();
    }

    private MetricValueResponse toMetricValue(MetricValueProjection projection) {
        int scale = projection.getValueScale();
        BigDecimal value = scaled(projection.getValue(), scale);
        BigDecimal prevValue = scaled(projection.getPrevValue(), scale);

        return new MetricValueResponse(
                projection.getMetricCode(),
                projection.getLabel(),
                value,
                projection.getUnit(),
                toYoy(value, prevValue));
    }

    /**
     * metric_value 는 NUMERIC(24,4) 라 금액도 {@code 71000000000000.0000} 으로 올라온다.
     * 명세는 {@code 71000000000000} 을 기대하므로 카탈로그의 value_scale 로 자릿수를 맞춘다.
     */
    private BigDecimal scaled(BigDecimal value, int scale) {
        return value == null ? null : value.setScale(scale, RoundingMode.HALF_UP);
    }

    /** 전년 행이 없으면 yoy 자체가 null 이다. 값은 있는데 비율만 못 내는 경우와 구분한다. */
    private YoyResponse toYoy(BigDecimal value, BigDecimal prevValue) {
        return prevValue == null ? null : new YoyResponse(prevValue, changeRate(value, prevValue));
    }

    private BigDecimal changeRate(BigDecimal value, BigDecimal prevValue) {
        if (value == null || prevValue == null || prevValue.signum() <= 0) {
            return null;
        }
        return value.subtract(prevValue)
                .multiply(HUNDRED)
                .divide(prevValue, RATE_SCALE, RoundingMode.HALF_UP);
    }
}

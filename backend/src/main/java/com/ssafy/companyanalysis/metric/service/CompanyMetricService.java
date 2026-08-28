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
import com.ssafy.companyanalysis.metric.dto.SingleMetricResponse;
import com.ssafy.companyanalysis.metric.dto.SingleMetricTimeseriesResponse;
import com.ssafy.companyanalysis.metric.dto.YoyResponse;
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

    /** 증감률 소수 자릿수. 명세 예시가 7.3 이라 1자리로 고정한다. */
    private static final int CHANGE_RATE_SCALE = 1;

    /** 명세가 정한 시계열 기본 구간. MVP 의 관심 구간이 2021~2025 다. */
    private static final int DEFAULT_FROM_YEAR = 2021;
    private static final int DEFAULT_TO_YEAR = 2025;

    private final CompanyRepository companyRepository;
    private final MetricRepository metricRepository;

    public CompanyMetricService(CompanyRepository companyRepository, MetricRepository metricRepository) {
        this.companyRepository = companyRepository;
        this.metricRepository = metricRepository;
    }

    /**
     * 한 기업의 지정 연도 지표 6종을 조회한다.
     *
     * @param year    null 이면 그 기업의 최신 적재 연도
     * @param withYoy false 면 yoy 를 계산하지 않고 null 로 내보낸다
     */
    @Transactional(readOnly = true)
    public CompanyMetricsResponse getMetrics(String corpCode, Integer year, boolean withYoy) {
        requireCompany(corpCode);

        Integer targetYear = resolveYear(corpCode, year);
        if (targetYear == null) {
            // 이 기업의 적재값이 하나도 없다. 조회할 연도가 없을 뿐 오류는 아니므로
            // 카탈로그만으로 6건의 골격을 만들어 준다.
            return new CompanyMetricsResponse(corpCode, null, emptyMetrics());
        }

        List<MetricValueResponse> metrics =
                metricRepository.findMetricValues(corpCode, targetYear, targetYear - 1).stream()
                        .map(projection -> toMetricValue(projection, withYoy))
                        .toList();

        return new CompanyMetricsResponse(corpCode, targetYear, metrics);
    }

    /**
     * 지표 하나만 조회한다. 통합 조회와 같은 값이 나와야 하므로 기준연도 결정 방식도 같다.
     *
     * @param metric 지표 슬러그. 지원하지 않는 값이면 400 METRIC_NOT_SUPPORTED
     */
    @Transactional(readOnly = true)
    public SingleMetricResponse getMetric(String corpCode, String metric, Integer year, boolean withYoy) {
        requireCompany(corpCode);
        Metric catalog = requireMetric(metric);

        Integer targetYear = resolveYear(corpCode, year);
        if (targetYear == null) {
            return toSingleMetric(corpCode, targetYear, emptyMetric(catalog));
        }

        MetricValueResponse value =
                metricRepository.findMetricValue(corpCode, catalog.getMetricCode(), targetYear, targetYear - 1)
                        .map(projection -> toMetricValue(projection, withYoy))
                        .orElseGet(() -> emptyMetric(catalog));

        return toSingleMetric(corpCode, targetYear, value);
    }

    /**
     * 지정 구간의 지표별 시계열을 조회한다(F-14).
     *
     * @param keys 조회할 지표 슬러그 목록. 비어 있으면 활성 지표 전체
     */
    @Transactional(readOnly = true)
    public MetricTimeseriesResponse getTimeseries(String corpCode, Integer from, Integer to, List<String> keys) {
        requireCompany(corpCode);

        MetricRangeResponse range = resolveRange(from, to);
        List<String> metricCodes = resolveKeys(keys);

        List<MetricSeriesResponse> series = toSeries(
                metricRepository.findMetricPoints(corpCode, metricCodes, range.from(), range.to()), range);

        return new MetricTimeseriesResponse(range, series);
    }

    /** 지표 하나의 시계열. 통합 조회에서 series 한 건을 잘라낸 것과 같다. */
    @Transactional(readOnly = true)
    public SingleMetricTimeseriesResponse getMetricTimeseries(String corpCode, String metric,
                                                              Integer from, Integer to) {
        requireCompany(corpCode);
        Metric catalog = requireMetric(metric);

        MetricRangeResponse range = resolveRange(from, to);

        List<MetricSeriesResponse> series = toSeries(
                metricRepository.findMetricPoints(corpCode, List.of(catalog.getMetricCode()),
                        range.from(), range.to()), range);
        MetricSeriesResponse found = series.isEmpty() ? emptySeries(catalog, range) : series.getFirst();

        return new SingleMetricTimeseriesResponse(
                corpCode, found.key(), found.label(), found.unit(), range, found.points());
    }

    /**
     * 지표 슬러그를 DB 의 metric_code 표기로 맞춘다.
     *
     * <p>명세서의 통합 조회 예시는 {@code rd_ratio}(snake_case)인데 개별 조회 페이지의
     * 슬러그 목록만 {@code rd-ratio}(kebab-case)로 적혀 있다. 어느 쪽으로 호출해도
     * 같은 지표를 가리키게 하고, 응답의 {@code metric} 필드는 DB 표기로 통일한다.
     */
    private String normalize(String metric) {
        return metric.trim().toLowerCase().replace('-', '_');
    }

    private Metric requireMetric(String metric) {
        return metricRepository.findByMetricCodeAndActiveTrue(normalize(metric))
                .orElseThrow(() -> new BusinessException(ErrorCode.METRIC_NOT_SUPPORTED));
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

    /**
     * 요청한 지표 슬러그를 검증해 metric_code 목록으로 바꾼다.
     *
     * <p>하나라도 카탈로그에 없으면 400 이다. 조용히 걸러내면 FE 는 오타를
     * "데이터가 없는 지표"로 오해하게 된다.
     */
    private List<String> resolveKeys(List<String> keys) {
        List<Metric> active = metricRepository.findByActiveTrueOrderByDisplayOrderAsc();
        List<String> supported = active.stream().map(Metric::getMetricCode).toList();

        if (keys == null || keys.isEmpty()) {
            return supported;
        }

        List<String> requested = keys.stream()
                .filter(key -> !key.isBlank())
                .map(this::normalize)
                .distinct()
                .toList();
        if (requested.isEmpty()) {
            return supported;
        }

        Set<String> supportedSet = Set.copyOf(supported);
        List<String> unsupported = requested.stream().filter(key -> !supportedSet.contains(key)).toList();
        if (!unsupported.isEmpty()) {
            throw new BusinessException(ErrorCode.METRIC_NOT_SUPPORTED,
                    "지원하지 않는 지표입니다: " + String.join(", ", unsupported));
        }
        return requested;
    }

    private List<MetricValueResponse> emptyMetrics() {
        return metricRepository.findByActiveTrueOrderByDisplayOrderAsc().stream()
                .map(this::emptyMetric)
                .toList();
    }

    private MetricValueResponse emptyMetric(Metric catalog) {
        return new MetricValueResponse(catalog.getMetricCode(), catalog.getNameKo(), null, catalog.getUnit(), null);
    }

    private MetricSeriesResponse emptySeries(Metric catalog, MetricRangeResponse range) {
        return new MetricSeriesResponse(catalog.getMetricCode(), catalog.getNameKo(), catalog.getUnit(),
                points(Map.of(), range));
    }

    private SingleMetricResponse toSingleMetric(String corpCode, Integer year, MetricValueResponse metric) {
        return new SingleMetricResponse(
                corpCode, metric.key(), metric.label(), year, metric.value(), metric.unit(), metric.yoy());
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

    /** 구간의 모든 연도를 오름차순으로 채운다. 값이 없는 해는 null 이다. */
    private List<MetricPointResponse> points(Map<Integer, BigDecimal> valuesByYear, MetricRangeResponse range) {
        return IntStream.rangeClosed(range.from(), range.to())
                .mapToObj(year -> new MetricPointResponse(year, valuesByYear.get(year)))
                .toList();
    }

    private MetricValueResponse toMetricValue(MetricValueProjection projection, boolean withYoy) {
        int scale = projection.getValueScale();
        BigDecimal value = scaled(projection.getValue(), scale);
        BigDecimal prevValue = scaled(projection.getPrevValue(), scale);

        return new MetricValueResponse(
                projection.getMetricCode(),
                projection.getLabel(),
                value,
                projection.getUnit(),
                withYoy ? toYoy(value, prevValue) : null);
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
        if (value == null || prevValue.signum() <= 0) {
            return null;
        }
        return value.subtract(prevValue)
                .multiply(HUNDRED)
                .divide(prevValue, CHANGE_RATE_SCALE, RoundingMode.HALF_UP);
    }
}

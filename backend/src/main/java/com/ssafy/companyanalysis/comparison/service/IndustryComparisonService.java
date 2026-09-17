package com.ssafy.companyanalysis.comparison.service;

import com.ssafy.companyanalysis.company.repository.CompanyDetailProjection;
import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.comparison.dto.IndustryComparisonResponse;
import com.ssafy.companyanalysis.comparison.repository.IndustryComparisonProjection;
import com.ssafy.companyanalysis.comparison.repository.IndustryComparisonRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.global.year.BaseYearResolver;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Service
public class IndustryComparisonService {

    /**
     * v2 명세가 정한 비교 지표 7종. 응답의 metrics 순서이자 values 맵의 키 순서다.
     *
     * <p>v1 은 4종이었고 v2 에서 revenue_growth 와 operating_margin 이 신설됐다. 둘은
     * company_metric 에 적재되는 값이 아니라 조회 시점에 계산하는 파생 지표다 — 단년 조회의
     * 수익성 블록과 같은 방식이고, 저장하면 재적재 때 원본과 어긋난다.
     */
    private static final List<String> DEFAULT_METRICS = List.of(
            "revenue", "revenue_growth", "operating_profit", "operating_margin",
            "employee_count", "average_salary", "rd_ratio");

    private static final String REVENUE = "revenue";
    private static final String REVENUE_GROWTH = "revenue_growth";
    private static final String OPERATING_PROFIT = "operating_profit";
    private static final String OPERATING_MARGIN = "operating_margin";

    /** 명세가 정한 상한. 대상 기업까지 네 곳이 한 화면에 들어가는 수다. */
    private static final int MAX_PEERS = 3;

    /** 비율 지표의 자릿수. 단년 조회의 수익성·증감률과 같게 맞춘다. */
    private static final BigDecimal HUNDRED = BigDecimal.valueOf(100);
    private static final int RATE_SCALE = 1;

    private final CompanyRepository companyRepository;
    private final IndustryComparisonRepository comparisonRepository;
    private final BaseYearResolver baseYearResolver;

    public IndustryComparisonService(CompanyRepository companyRepository,
                                     IndustryComparisonRepository comparisonRepository,
                                     BaseYearResolver baseYearResolver) {
        this.companyRepository = companyRepository;
        this.comparisonRepository = comparisonRepository;
        this.baseYearResolver = baseYearResolver;
    }

    /**
     * 대상 기업과 사용자가 고른 기업들의 지표를 나란히 반환한다(v2).
     *
     * <p>v1 은 같은 산업 기업을 전부 실었다. v2 명세가 "사용자가 고른 peers(최대 3) 비교"로
     * 바꿔서, 이제 응답에는 대상 기업과 peers 만 담긴다. 비교할 기업을 고르는 목록은
     * {@code GET /api/industries/{industryCode}/companies} 가 따로 준다.
     *
     * <p>현재 기업은 값이 없어도 항상 리스트에 포함하고 {@code isTarget} 으로 표시한다(F-11·F-14).
     * 존재하지 않는 기업이면 404 COMPANY_NOT_FOUND 다.
     *
     * <p>{@code year} 를 주지 않으면 {@link BaseYearResolver} 가 정한 기준연도다. 그 해에
     * 적재된 값이 없는 기업은 지표가 전부 null 이고, 이는 오류가 아니다.
     *
     * @param peers   비교할 기업의 corpCode. 최대 3개이며, 넘으면 400 INVALID_PARAMETER
     * @param metrics 볼 지표 슬러그. 비우면 7종 전부. 7종 밖이면 400 METRIC_NOT_SUPPORTED
     */
    @Transactional(readOnly = true)
    public IndustryComparisonResponse compare(String corpCode, List<String> peers,
                                              List<String> metrics, Integer year) {
        CompanyDetailProjection target = companyRepository.findDetailByCorpCode(corpCode)
                .orElseThrow(() -> new BusinessException(ErrorCode.COMPANY_NOT_FOUND));

        List<String> resolvedMetrics = resolveMetrics(metrics);
        List<String> resolvedPeers = resolvePeers(peers, corpCode);
        int resolvedYear = year != null ? year : baseYearResolver.resolve();
        String division = target.getIndustryCode();

        List<String> corpCodes = new ArrayList<>();
        corpCodes.add(corpCode);
        corpCodes.addAll(resolvedPeers);

        List<IndustryComparisonProjection> rows = comparisonRepository.findValues(
                corpCodes, sourcesFor(resolvedMetrics), resolvedYear, resolvedYear - 1);

        List<IndustryComparisonResponse.Company> companies =
                buildCompanies(rows, corpCodes, corpCode, target.getCorpName(), resolvedMetrics, resolvedYear);

        IndustryComparisonResponse.Industry industry = new IndustryComparisonResponse.Industry(
                division, target.getIndustryName(),
                division == null ? 0 : (int) comparisonRepository.countByIndustry(division));

        return new IndustryComparisonResponse(resolvedYear, industry, resolvedMetrics, companies);
    }

    /**
     * 볼 지표를 정한다. 비어 있으면 7종 전부다.
     *
     * <p>하나라도 7종 밖이면 400 이다. 조용히 걸러내면 FE 는 오타를 "데이터가 없는 지표"로
     * 오해한다. 단년 조회의 {@code keys} 와 같은 판단이다.
     *
     * <p>반환 순서는 요청한 순서가 아니라 명세가 정한 7종 순서다. 화면이 같은 지표를 늘
     * 같은 자리에 그릴 수 있어야 한다.
     */
    private List<String> resolveMetrics(List<String> metrics) {
        List<String> requested = metrics == null ? List.of() : metrics.stream()
                .filter(key -> key != null && !key.isBlank())
                .map(key -> key.trim().replace('-', '_'))
                .distinct()
                .toList();

        if (requested.isEmpty()) {
            return DEFAULT_METRICS;
        }

        List<String> unsupported = requested.stream().filter(key -> !DEFAULT_METRICS.contains(key)).toList();
        if (!unsupported.isEmpty()) {
            throw new BusinessException(ErrorCode.METRIC_NOT_SUPPORTED,
                    "지원하지 않는 지표입니다: " + String.join(", ", unsupported));
        }

        Set<String> wanted = Set.copyOf(requested);
        return DEFAULT_METRICS.stream().filter(wanted::contains).toList();
    }

    /**
     * 비교할 기업 목록을 정리한다. 중복과 대상 기업 자신은 빼고, 남은 수가 3을 넘으면 400 이다.
     *
     * <p>대상 기업을 peers 로 다시 보내는 것은 오류로 보지 않는다. 화면이 목록에서 고르다 보면
     * 자기 자신이 섞일 수 있고, 결과는 어차피 한 번만 실리면 되기 때문이다.
     *
     * <p>존재하지 않는 corpCode 는 여기서 막지 않고 조회에서 자연스럽게 빠진다. 후보 목록이
     * 낡아 없는 기업 하나가 섞였다고 비교 화면 전체가 400 이 되면 안 된다. 어느 기업이
     * 빠졌는지는 응답의 companies 를 보면 알 수 있다.
     */
    private List<String> resolvePeers(List<String> peers, String targetCorpCode) {
        if (peers == null) {
            return List.of();
        }

        List<String> resolved = peers.stream()
                .filter(code -> code != null && !code.isBlank())
                .map(String::trim)
                .distinct()
                .filter(code -> !code.equals(targetCorpCode))
                .toList();

        if (resolved.size() > MAX_PEERS) {
            throw new BusinessException(ErrorCode.INVALID_PARAMETER,
                    "비교 기업은 최대 " + MAX_PEERS + "곳입니다.");
        }
        return resolved;
    }

    /**
     * 요청한 지표를 계산하는 데 필요한 적재 지표를 모은다.
     *
     * <p>매출 성장률은 매출이, 영업이익률은 영업이익과 매출이 원본이다. 나머지는 슬러그가
     * 그대로 metric_code 다. 파생 지표를 그대로 조회에 넘기면 company_metric 에 없는 코드라
     * 늘 빈 결과가 된다.
     */
    private Set<String> sourcesFor(List<String> metrics) {
        Set<String> sources = new LinkedHashSet<>();
        for (String metric : metrics) {
            switch (metric) {
                case REVENUE_GROWTH -> sources.add(REVENUE);
                case OPERATING_MARGIN -> {
                    sources.add(OPERATING_PROFIT);
                    sources.add(REVENUE);
                }
                default -> sources.add(metric);
            }
        }
        return sources;
    }

    /**
     * 행 단위 결과를 기업 단위로 묶는다. 대상 기업이 맨 앞이고 그 뒤는 peers 를 받은 순서다.
     *
     * <p>조회에서 빠진 기업(존재하지 않는 corpCode)은 목록에도 없다. 대상 기업만은 값이
     * 하나도 없어도 반드시 남는다.
     */
    private List<IndustryComparisonResponse.Company> buildCompanies(
            List<IndustryComparisonProjection> rows, List<String> corpCodes,
            String targetCorpCode, String targetCorpName, List<String> metrics, int year) {

        Map<String, String> nameByCompany = new LinkedHashMap<>();
        Map<String, Map<String, BigDecimal>> currentByCompany = new LinkedHashMap<>();
        Map<String, Map<String, BigDecimal>> previousByCompany = new LinkedHashMap<>();
        Map<String, Short> scaleByMetric = new LinkedHashMap<>();

        for (IndustryComparisonProjection row : rows) {
            nameByCompany.putIfAbsent(row.getCorpCode(), row.getCorpName());
            if (row.getMetricCode() == null || row.getFiscalYear() == null) {
                continue;
            }
            if (row.getValueScale() != null) {
                scaleByMetric.putIfAbsent(row.getMetricCode(), row.getValueScale());
            }
            Map<String, Map<String, BigDecimal>> bucket =
                    row.getFiscalYear() == year ? currentByCompany : previousByCompany;
            bucket.computeIfAbsent(row.getCorpCode(), key -> new LinkedHashMap<>())
                    .put(row.getMetricCode(), row.getValue());
        }

        // 대상 기업은 조회 결과에 행이 없어도(적재 연도가 없어 조회 자체를 건너뛴 경우 포함) 남는다.
        nameByCompany.putIfAbsent(targetCorpCode, targetCorpName);

        List<IndustryComparisonResponse.Company> companies = new ArrayList<>();
        for (String code : corpCodes) {
            if (!nameByCompany.containsKey(code)) {
                continue;
            }
            companies.add(new IndustryComparisonResponse.Company(
                    code,
                    nameByCompany.get(code),
                    code.equals(targetCorpCode),
                    values(metrics,
                            currentByCompany.getOrDefault(code, Map.of()),
                            previousByCompany.getOrDefault(code, Map.of()),
                            scaleByMetric)));
        }
        return companies;
    }

    /** 요청한 지표를 순서대로 채운다. 계산할 원본이 없으면 자리는 두고 null 이다(F-12). */
    private Map<String, BigDecimal> values(List<String> metrics,
                                           Map<String, BigDecimal> current,
                                           Map<String, BigDecimal> previous,
                                           Map<String, Short> scaleByMetric) {
        Map<String, BigDecimal> values = new LinkedHashMap<>();
        for (String metric : metrics) {
            values.put(metric, switch (metric) {
                case REVENUE_GROWTH -> changeRate(current.get(REVENUE), previous.get(REVENUE));
                case OPERATING_MARGIN -> ratio(current.get(OPERATING_PROFIT), current.get(REVENUE));
                default -> scaled(current.get(metric), scaleByMetric.get(metric));
            });
        }
        return values;
    }

    /** metric_value 는 NUMERIC(24,4) 라 카탈로그의 value_scale 로 자릿수를 맞춘다(단년 조회와 동일 규칙). */
    private BigDecimal scaled(BigDecimal value, Short scale) {
        if (value == null) {
            return null;
        }
        return value.setScale(scale != null ? scale : 0, RoundingMode.HALF_UP);
    }

    /**
     * 백분율을 만든다. 분모가 없거나 0 이하면 null 이다.
     *
     * <p>적자 기업의 영업이익률은 분자가 음수라 그대로 계산해도 뜻이 통하지만, 매출이 0 이면
     * 비율 자체가 성립하지 않는다. 단년 조회의 수익성 계산과 같은 규칙이다.
     */
    private BigDecimal ratio(BigDecimal numerator, BigDecimal denominator) {
        if (numerator == null || denominator == null || denominator.signum() <= 0) {
            return null;
        }
        return numerator.multiply(HUNDRED).divide(denominator, RATE_SCALE, RoundingMode.HALF_UP);
    }

    /** 전년 매출이 없거나 0 이하면 성장률을 내지 않는다. 부호가 뒤집혀 역성장이 성장처럼 보인다. */
    private BigDecimal changeRate(BigDecimal value, BigDecimal prevValue) {
        if (value == null || prevValue == null || prevValue.signum() <= 0) {
            return null;
        }
        return value.subtract(prevValue)
                .multiply(HUNDRED)
                .divide(prevValue, RATE_SCALE, RoundingMode.HALF_UP);
    }
}

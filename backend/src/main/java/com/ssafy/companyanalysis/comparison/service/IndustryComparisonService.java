package com.ssafy.companyanalysis.comparison.service;

import com.ssafy.companyanalysis.company.repository.CompanyDetailProjection;
import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.comparison.dto.IndustryComparisonResponse;
import com.ssafy.companyanalysis.comparison.repository.IndustryComparisonProjection;
import com.ssafy.companyanalysis.comparison.repository.IndustryComparisonRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class IndustryComparisonService {

    /** 명세가 정한 비교 지표 4종. 응답의 metrics 순서이자 values 맵의 키 순서다. */
    private static final List<String> METRIC_CODES =
            List.of("revenue", "operating_profit", "employee_count", "average_salary");

    private final CompanyRepository companyRepository;
    private final IndustryComparisonRepository comparisonRepository;

    public IndustryComparisonService(CompanyRepository companyRepository,
                                     IndustryComparisonRepository comparisonRepository) {
        this.companyRepository = companyRepository;
        this.comparisonRepository = comparisonRepository;
    }

    /**
     * 같은 KSIC 중분류 기업들의 지정 연도 비교값을 반환한다.
     *
     * <p>현재 기업은 값이 없어도 항상 리스트에 포함하고 {@code isTarget} 으로 표시한다(F-11·F-14).
     * 존재하지 않는 기업이면 404 COMPANY_NOT_FOUND 다.
     *
     * <p>{@code year} 를 주지 않으면 대상 기업의 최신 적재 연도({@code dataYear})로 맞춘다.
     * 여기서 특정 연도를 상수로 박으면 적재가 한 해 밀릴 때마다 상세·지표와 다른 해를
     * 비교하게 되므로, 기준은 데이터에서만 온다. 적재된 값이 하나도 없으면 응답의
     * {@code year} 는 null 이고 비교군도 비어 있다 — 지표 조회가 같은 상황에서 하는 것과 같다.
     */
    @Transactional(readOnly = true)
    public IndustryComparisonResponse compare(String corpCode, Integer year) {
        CompanyDetailProjection target = companyRepository.findDetailByCorpCode(corpCode)
                .orElseThrow(() -> new BusinessException(ErrorCode.COMPANY_NOT_FOUND));

        Integer resolvedYear = year != null ? year : target.getDataYear();
        String division = target.getIndustryCode();

        List<IndustryComparisonProjection> rows = division == null || resolvedYear == null
                ? List.of()
                : comparisonRepository.findComparison(division, resolvedYear, METRIC_CODES);

        List<IndustryComparisonResponse.Company> companies =
                pivot(rows, corpCode, target.getCorpName());

        IndustryComparisonResponse.Industry industry = new IndustryComparisonResponse.Industry(
                division, target.getIndustryName(), companies.size());

        return new IndustryComparisonResponse(resolvedYear, industry, METRIC_CODES, companies);
    }

    /** 행 단위 결과를 기업 단위로 묶는다. 대상 기업을 맨 앞에 두고 나머지는 corp_name 순을 유지한다. */
    private List<IndustryComparisonResponse.Company> pivot(List<IndustryComparisonProjection> rows,
                                                           String targetCorpCode, String targetCorpName) {
        Map<String, String> nameByCompany = new LinkedHashMap<>();
        Map<String, Map<String, BigDecimal>> valuesByCompany = new LinkedHashMap<>();

        for (IndustryComparisonProjection row : rows) {
            nameByCompany.putIfAbsent(row.getCorpCode(), row.getCorpName());
            Map<String, BigDecimal> values =
                    valuesByCompany.computeIfAbsent(row.getCorpCode(), k -> emptyValues());
            if (row.getMetricCode() != null) {
                values.put(row.getMetricCode(), scaled(row.getValue(), row.getValueScale()));
            }
        }

        // 대상 기업의 값이 하나도 없으면 위 루프에서 빠졌을 수 있다. 항상 포함해야 한다.
        nameByCompany.putIfAbsent(targetCorpCode, targetCorpName);
        valuesByCompany.computeIfAbsent(targetCorpCode, k -> emptyValues());

        List<IndustryComparisonResponse.Company> companies = new ArrayList<>();
        companies.add(new IndustryComparisonResponse.Company(
                targetCorpCode, nameByCompany.get(targetCorpCode), true, valuesByCompany.get(targetCorpCode)));

        for (Map.Entry<String, Map<String, BigDecimal>> entry : valuesByCompany.entrySet()) {
            if (entry.getKey().equals(targetCorpCode)) {
                continue;
            }
            companies.add(new IndustryComparisonResponse.Company(
                    entry.getKey(), nameByCompany.get(entry.getKey()), false, entry.getValue()));
        }
        return companies;
    }

    /** 4종 지표를 순서대로 null 로 채운 맵. 값이 있는 지표만 나중에 덮어쓴다. */
    private Map<String, BigDecimal> emptyValues() {
        Map<String, BigDecimal> values = new LinkedHashMap<>();
        for (String code : METRIC_CODES) {
            values.put(code, null);
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
}

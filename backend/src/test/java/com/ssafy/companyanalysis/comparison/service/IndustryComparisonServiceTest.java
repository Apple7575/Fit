package com.ssafy.companyanalysis.comparison.service;

import com.ssafy.companyanalysis.company.repository.CompanyDetailProjection;
import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.comparison.dto.IndustryComparisonResponse;
import com.ssafy.companyanalysis.comparison.repository.IndustryComparisonProjection;
import com.ssafy.companyanalysis.comparison.repository.IndustryComparisonRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
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
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;

class IndustryComparisonServiceTest {

    private static final String TARGET = "00164779";

    private CompanyRepository companyRepository;
    private IndustryComparisonRepository comparisonRepository;
    private IndustryComparisonService service;

    @BeforeEach
    void setUp() {
        companyRepository = mock(CompanyRepository.class);
        comparisonRepository = mock(IndustryComparisonRepository.class);
        service = new IndustryComparisonService(companyRepository, comparisonRepository);
    }

    @Test
    @DisplayName("행 단위 결과를 기업 단위로 묶고 대상 기업을 맨 앞에 표시한다")
    void pivotsRowsAndFlagsTarget() {
        CompanyDetailProjection target = target("26", "전자 부품 제조업");
        List<IndustryComparisonProjection> rows = List.of(
                row("00126380", "삼성전자", "revenue", new BigDecimal("300870000000000.0000"), (short) 0),
                row(TARGET, "SK하이닉스", "revenue", new BigDecimal("71000000000000.0000"), (short) 0),
                row(TARGET, "SK하이닉스", "employee_count", new BigDecimal("31000.0000"), (short) 0));
        given(companyRepository.findDetailByCorpCode(TARGET)).willReturn(Optional.of(target));
        given(comparisonRepository.findComparison(eq("26"), anyInt(), any())).willReturn(rows);

        IndustryComparisonResponse response = service.compare(TARGET, 2025);

        assertThat(response.year()).isEqualTo(2025);
        assertThat(response.industry().code()).isEqualTo("26");
        assertThat(response.industry().companyCount()).isEqualTo(2);
        assertThat(response.metrics())
                .containsExactly("revenue", "operating_profit", "employee_count", "average_salary");

        IndustryComparisonResponse.Company first = response.companies().get(0);
        assertThat(first.corpCode()).isEqualTo(TARGET);
        assertThat(first.isTarget()).isTrue();
        // NUMERIC(24,4) 원본이 value_scale 0 으로 정리된다
        assertThat(first.values().get("revenue")).isEqualByComparingTo("71000000000000");
        assertThat(first.values().get("employee_count")).isEqualByComparingTo("31000");
        // 값이 없는 지표도 키는 유지하되 null (0 변환 금지)
        assertThat(first.values()).containsKey("operating_profit");
        assertThat(first.values().get("operating_profit")).isNull();

        assertThat(response.companies().get(1).isTarget()).isFalse();
    }

    @Test
    @DisplayName("year 를 안 주면 그 기업의 최신 적재 연도로 조회한다")
    void defaultsYearToCompanyDataYear() {
        CompanyDetailProjection target = target("26", "전자 부품 제조업", 2024);
        given(companyRepository.findDetailByCorpCode(TARGET)).willReturn(Optional.of(target));
        given(comparisonRepository.findComparison(eq("26"), eq(2024), any())).willReturn(List.of());

        IndustryComparisonResponse response = service.compare(TARGET, null);

        assertThat(response.year()).isEqualTo(2024);
    }

    @Test
    @DisplayName("적재된 값이 없는 기업은 year 가 null 이고 비교 조회를 타지 않는다")
    void nullYearWhenCompanyHasNoData() {
        CompanyDetailProjection target = target("26", "전자 부품 제조업", null);
        given(companyRepository.findDetailByCorpCode(TARGET)).willReturn(Optional.of(target));

        IndustryComparisonResponse response = service.compare(TARGET, null);

        assertThat(response.year()).isNull();
        assertThat(response.companies()).hasSize(1);
        assertThat(response.companies().getFirst().isTarget()).isTrue();
        verifyNoInteractions(comparisonRepository);
    }

    @Test
    @DisplayName("비교 대상이 없어도 대상 기업만 담아 반환한다")
    void alwaysIncludesTarget() {
        CompanyDetailProjection target = target("26", "전자 부품 제조업");
        given(companyRepository.findDetailByCorpCode(TARGET)).willReturn(Optional.of(target));
        given(comparisonRepository.findComparison(eq("26"), anyInt(), any())).willReturn(List.of());

        IndustryComparisonResponse response = service.compare(TARGET, 2025);

        assertThat(response.companies()).hasSize(1);
        assertThat(response.companies().get(0).corpCode()).isEqualTo(TARGET);
        assertThat(response.companies().get(0).isTarget()).isTrue();
        assertThat(response.companies().get(0).values().get("revenue")).isNull();
        assertThat(response.industry().companyCount()).isEqualTo(1);
    }

    @Test
    @DisplayName("없는 기업은 COMPANY_NOT_FOUND 로 예외를 던진다")
    void unknownCompanyThrows() {
        given(companyRepository.findDetailByCorpCode("00000000")).willReturn(Optional.empty());

        assertThatThrownBy(() -> service.compare("00000000", 2025))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.COMPANY_NOT_FOUND);
    }

    private CompanyDetailProjection target(String industryCode, String industryName) {
        return target(industryCode, industryName, 2025);
    }

    private CompanyDetailProjection target(String industryCode, String industryName, Integer dataYear) {
        CompanyDetailProjection p = mock(CompanyDetailProjection.class);
        given(p.getCorpCode()).willReturn(TARGET);
        given(p.getCorpName()).willReturn("SK하이닉스");
        given(p.getIndustryCode()).willReturn(industryCode);
        given(p.getIndustryName()).willReturn(industryName);
        given(p.getDataYear()).willReturn(dataYear);
        return p;
    }

    private IndustryComparisonProjection row(String corpCode, String corpName,
                                             String metricCode, BigDecimal value, Short valueScale) {
        IndustryComparisonProjection p = mock(IndustryComparisonProjection.class);
        given(p.getCorpCode()).willReturn(corpCode);
        given(p.getCorpName()).willReturn(corpName);
        given(p.getMetricCode()).willReturn(metricCode);
        given(p.getValue()).willReturn(value);
        given(p.getValueScale()).willReturn(valueScale);
        return p;
    }
}

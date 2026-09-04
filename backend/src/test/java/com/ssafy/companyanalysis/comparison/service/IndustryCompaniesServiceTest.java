package com.ssafy.companyanalysis.comparison.service;

import com.ssafy.companyanalysis.company.domain.Industry;
import com.ssafy.companyanalysis.comparison.dto.IndustryCompaniesResponse;
import com.ssafy.companyanalysis.comparison.repository.IndustryCompanyProjection;
import com.ssafy.companyanalysis.comparison.repository.IndustryCompanyRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.metric.domain.Metric;
import com.ssafy.companyanalysis.metric.repository.MetricRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verifyNoInteractions;

class IndustryCompaniesServiceTest {

    private static final String DIVISION = "26";

    private IndustryCompanyRepository industryCompanyRepository;
    private MetricRepository metricRepository;
    private IndustryCompaniesService service;

    /**
     * 목을 만드는 헬퍼는 안에서 다시 {@code given} 을 부르므로, 헬퍼 호출을 다른 {@code given} 의
     * 인자 자리에 두면 스터빙이 겹쳐 UnfinishedStubbingException 이 난다. 늘 지역변수로 먼저 만든다.
     */
    @BeforeEach
    void setUp() {
        industryCompanyRepository = mock(IndustryCompanyRepository.class);
        metricRepository = mock(MetricRepository.class);
        service = new IndustryCompaniesService(industryCompanyRepository, metricRepository);
    }

    @Test
    @DisplayName("산업과 후보 기업을 조회 순서 그대로 담아 반환한다")
    void returnsIndustryAndCandidatesInQueryOrder() {
        Industry industry = industry(DIVISION, "전자 부품 제조업");
        List<IndustryCompanyProjection> rows =
                List.of(candidate("00126380", "삼성전자"), candidate("00164779", "SK하이닉스"));
        given(industryCompanyRepository.findByIndustryCode(DIVISION)).willReturn(Optional.of(industry));
        given(industryCompanyRepository.findCandidates(eq(DIVISION), eq("revenue"), anyInt()))
                .willReturn(rows);

        IndustryCompaniesResponse response = service.listCandidates(DIVISION, null, 50);

        assertThat(response.industry().code()).isEqualTo(DIVISION);
        assertThat(response.industry().name()).isEqualTo("전자 부품 제조업");
        assertThat(response.companies())
                .extracting(IndustryCompaniesResponse.Company::corpName)
                .containsExactly("삼성전자", "SK하이닉스");
    }

    @Test
    @DisplayName("sort 를 주지 않으면 revenue 로 정렬한다")
    void defaultSortIsRevenue() {
        Industry industry = industry(DIVISION, "전자 부품 제조업");
        given(industryCompanyRepository.findByIndustryCode(DIVISION)).willReturn(Optional.of(industry));
        given(industryCompanyRepository.findCandidates(anyString(), anyString(), anyInt()))
                .willReturn(List.of());

        service.listCandidates(DIVISION, null, 50);

        then(industryCompanyRepository).should().findCandidates(DIVISION, "revenue", 50);
        // 기본값은 카탈로그를 확인할 필요가 없다. 명세가 정한 값이라 이미 지원 지표다.
        verifyNoInteractions(metricRepository);
    }

    @Test
    @DisplayName("빈 문자열 sort 도 기본값으로 본다")
    void blankSortFallsBackToDefault() {
        Industry industry = industry(DIVISION, "전자 부품 제조업");
        given(industryCompanyRepository.findByIndustryCode(DIVISION)).willReturn(Optional.of(industry));
        given(industryCompanyRepository.findCandidates(anyString(), anyString(), anyInt()))
                .willReturn(List.of());

        service.listCandidates(DIVISION, "  ", 50);

        then(industryCompanyRepository).should().findCandidates(DIVISION, "revenue", 50);
    }

    @Test
    @DisplayName("카탈로그에 있는 지표는 정렬 기준으로 그대로 넘긴다")
    void supportedSortIsPassedThrough() {
        List<Metric> catalog = List.of(metric("revenue"), metric("employee_count"));
        Industry industry = industry(DIVISION, "전자 부품 제조업");
        given(metricRepository.findByActiveTrueOrderByDisplayOrderAsc()).willReturn(catalog);
        given(industryCompanyRepository.findByIndustryCode(DIVISION)).willReturn(Optional.of(industry));
        given(industryCompanyRepository.findCandidates(anyString(), anyString(), anyInt()))
                .willReturn(List.of());

        service.listCandidates(DIVISION, "employee_count", 20);

        then(industryCompanyRepository).should().findCandidates(DIVISION, "employee_count", 20);
    }

    @Test
    @DisplayName("카탈로그에 없는 지표로 정렬하면 400 INVALID_PARAMETER 이고 조회는 시작하지 않는다")
    void unsupportedSortIsRejectedBeforeQuery() {
        List<Metric> catalog = List.of(metric("revenue"));
        given(metricRepository.findByActiveTrueOrderByDisplayOrderAsc()).willReturn(catalog);

        assertThatThrownBy(() -> service.listCandidates(DIVISION, "없는지표", 50))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.INVALID_PARAMETER);

        then(industryCompanyRepository).should(never()).findCandidates(anyString(), anyString(), anyInt());
    }

    @Test
    @DisplayName("없는 industryCode 는 예외가 아니라 industry null 과 빈 배열이다")
    void unknownIndustryReturnsEmptyList() {
        given(industryCompanyRepository.findByIndustryCode("99")).willReturn(Optional.empty());

        IndustryCompaniesResponse response = service.listCandidates("99", null, 50);

        assertThat(response.industry()).isNull();
        assertThat(response.companies()).isEmpty();
        // 산업이 없으면 기업 조회를 아예 하지 않는다.
        then(industryCompanyRepository).should(never()).findCandidates(anyString(), anyString(), anyInt());
    }

    @Test
    @DisplayName("산업은 있는데 소속 기업이 없으면 산업 정보와 빈 배열을 함께 반환한다")
    void knownIndustryWithNoCompaniesKeepsIndustryBlock() {
        Industry industry = industry(DIVISION, "전자 부품 제조업");
        given(industryCompanyRepository.findByIndustryCode(DIVISION)).willReturn(Optional.of(industry));
        given(industryCompanyRepository.findCandidates(anyString(), anyString(), anyInt()))
                .willReturn(List.of());

        IndustryCompaniesResponse response = service.listCandidates(DIVISION, null, 50);

        assertThat(response.industry().code()).isEqualTo(DIVISION);
        assertThat(response.companies()).isEmpty();
    }

    private static Industry industry(String code, String name) {
        Industry industry = mock(Industry.class);
        given(industry.getIndustryCode()).willReturn(code);
        given(industry.getIndustryName()).willReturn(name);
        return industry;
    }

    private static Metric metric(String code) {
        Metric metric = mock(Metric.class);
        given(metric.getMetricCode()).willReturn(code);
        return metric;
    }

    private static IndustryCompanyProjection candidate(String corpCode, String corpName) {
        IndustryCompanyProjection row = mock(IndustryCompanyProjection.class);
        given(row.getCorpCode()).willReturn(corpCode);
        given(row.getCorpName()).willReturn(corpName);
        return row;
    }
}

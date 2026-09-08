package com.ssafy.companyanalysis.focus.service;

import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.focus.dto.CompanySegmentsResponse;
import com.ssafy.companyanalysis.focus.repository.CompanySegmentChangeRepository;
import com.ssafy.companyanalysis.focus.repository.SegmentChangeProjection;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.metric.repository.MetricRepository;
import com.ssafy.companyanalysis.metric.repository.MetricValueProjection;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

/**
 * 증감 계산과 기준연도 결정을 검증한다.
 *
 * <p>전사 증감이 부문 증감의 합과 다른 것이 이 API 의 핵심이라, 그 차이가 실제로 유지되는지를
 * 특히 본다. 합이 맞도록 고치는 순간 미공시 부문의 몫이 사라진다.
 */
class CompanySegmentsServiceTest {

    private static final String CORP_CODE = "00126380";

    private CompanyRepository companyRepository;
    private CompanySegmentChangeRepository segmentRepository;
    private MetricRepository metricRepository;
    private CompanySegmentsService service;

    @BeforeEach
    void setUp() {
        companyRepository = mock(CompanyRepository.class);
        segmentRepository = mock(CompanySegmentChangeRepository.class);
        metricRepository = mock(MetricRepository.class);
        service = new CompanySegmentsService(companyRepository, segmentRepository, metricRepository);

        given(companyRepository.existsById(CORP_CODE)).willReturn(true);
    }

    @Test
    @DisplayName("부문 비중과 인력 증감을 계산하고 전사 증감은 지표에서 가져온다")
    void computesSharesAndChanges() {
        given(segmentRepository.findLatestFiscalYear(eq(CORP_CODE), any())).willReturn(2025);
        List<SegmentChangeProjection> rows = List.of(
                segment("DS", "232000000000000", 75000, 73000),
                segment("DX", "168000000000000", 55000, 56000));
        given(segmentRepository.findSegmentChanges(CORP_CODE, 2025, 2024)).willReturn(rows);
        List<MetricValueProjection> metrics = List.of(metric("125000", "124000"));
        given(metricRepository.findMetricValues(CORP_CODE, List.of("employee_count"), 2025, 2024))
                .willReturn(metrics);

        CompanySegmentsResponse response = service.getSegments(CORP_CODE, null);

        assertThat(response.year()).isEqualTo(2025);
        assertThat(response.segments()).extracting(CompanySegmentsResponse.Segment::name)
                .containsExactly("DS", "DX");
        assertThat(response.segments().get(0).revenueShare()).isEqualByComparingTo("58.0");
        assertThat(response.segments().get(0).employeeChange()).isEqualTo(2000);
        assertThat(response.segments().get(1).revenueShare()).isEqualByComparingTo("42.0");
        assertThat(response.segments().get(1).employeeChange()).isEqualTo(-1000);
        // 부문 증감의 합은 1000 이지만 전사는 1000 이 아니다. 맞추려 들지 않는다.
        assertThat(response.employeeTotalChange()).isEqualTo(1000);
    }

    @Test
    @DisplayName("전사 증감이 부문 증감의 합과 달라도 그대로 내보낸다")
    void totalChangeIsNotReconciledWithSegmentSum() {
        given(segmentRepository.findLatestFiscalYear(eq(CORP_CODE), any())).willReturn(2025);
        List<SegmentChangeProjection> rows = List.of(segment("DS", "1000", 100, 90));
        given(segmentRepository.findSegmentChanges(CORP_CODE, 2025, 2024)).willReturn(rows);
        List<MetricValueProjection> metrics = List.of(metric("500", "400"));
        given(metricRepository.findMetricValues(eq(CORP_CODE), any(), eq(2025), eq(2024)))
                .willReturn(metrics);

        CompanySegmentsResponse response = service.getSegments(CORP_CODE, null);

        assertThat(response.segments().get(0).employeeChange()).isEqualTo(10);
        // 부문에서 공시하지 않은 인력이 전사 숫자에는 들어 있다.
        assertThat(response.employeeTotalChange()).isEqualTo(100);
    }

    @Test
    @DisplayName("전년 인원이 없는 부문은 증감을 내지 않는다 (0 에서 늘어난 것으로 보지 않는다)")
    void newSegmentHasNullEmployeeChange() {
        given(segmentRepository.findLatestFiscalYear(eq(CORP_CODE), any())).willReturn(2025);
        List<SegmentChangeProjection> rows = List.of(segment("NEW", "1000", 500, null));
        given(segmentRepository.findSegmentChanges(CORP_CODE, 2025, 2024)).willReturn(rows);

        CompanySegmentsResponse response = service.getSegments(CORP_CODE, null);

        assertThat(response.segments().get(0).employeeChange()).isNull();
    }

    @Test
    @DisplayName("매출·인력을 공시하지 않은 부문도 목록에 남고 값만 null 이다")
    void undisclosedSegmentKeepsItsSlot() {
        given(segmentRepository.findLatestFiscalYear(eq(CORP_CODE), any())).willReturn(2025);
        List<SegmentChangeProjection> rows = List.of(
                segment("DS", "1000", 100, 90),
                segment("SDC", null, null, null));
        given(segmentRepository.findSegmentChanges(CORP_CODE, 2025, 2024)).willReturn(rows);

        CompanySegmentsResponse response = service.getSegments(CORP_CODE, null);

        assertThat(response.segments()).hasSize(2);
        assertThat(response.segments().get(1).name()).isEqualTo("SDC");
        assertThat(response.segments().get(1).revenue()).isNull();
        assertThat(response.segments().get(1).revenueShare()).isNull();
        assertThat(response.segments().get(1).employeeChange()).isNull();
    }

    @Test
    @DisplayName("전사 직원 수만 적재된 기업도 200 이고 전사 증감만 채워진다")
    void metricOnlyCompanyStillReturnsTotalChange() {
        given(segmentRepository.findLatestFiscalYear(eq(CORP_CODE), any())).willReturn(2025);
        given(segmentRepository.findSegmentChanges(CORP_CODE, 2025, 2024)).willReturn(List.of());
        List<MetricValueProjection> metrics = List.of(metric("125000", "124000"));
        given(metricRepository.findMetricValues(eq(CORP_CODE), any(), eq(2025), eq(2024)))
                .willReturn(metrics);

        CompanySegmentsResponse response = service.getSegments(CORP_CODE, null);

        assertThat(response.segments()).isEmpty();
        assertThat(response.employeeTotalChange()).isEqualTo(1000);
    }

    @Test
    @DisplayName("전년 직원 수가 없으면 전사 증감은 null 이다")
    void nullTotalChangeWithoutPreviousYear() {
        given(segmentRepository.findLatestFiscalYear(eq(CORP_CODE), any())).willReturn(2025);
        List<MetricValueProjection> metrics = List.of(metric("125000", null));
        given(metricRepository.findMetricValues(eq(CORP_CODE), any(), eq(2025), eq(2024)))
                .willReturn(metrics);

        assertThat(service.getSegments(CORP_CODE, null).employeeTotalChange()).isNull();
    }

    @Test
    @DisplayName("부문도 직원 수도 한 해도 없으면 year 는 null 이고 목록은 빈 배열이다")
    void emptyWhenNothingLoaded() {
        given(segmentRepository.findLatestFiscalYear(eq(CORP_CODE), any())).willReturn(null);

        CompanySegmentsResponse response = service.getSegments(CORP_CODE, null);

        assertThat(response.year()).isNull();
        assertThat(response.employeeTotalChange()).isNull();
        assertThat(response.segments()).isEmpty();
        verify(segmentRepository, never()).findSegmentChanges(anyString(), anyInt(), anyInt());
        verify(metricRepository, never()).findMetricValues(anyString(), any(), anyInt(), anyInt());
    }

    @Test
    @DisplayName("요청한 연도에 데이터가 없어도 최신 연도로 갈아타지 않는다")
    void requestedYearIsNotSilentlyReplaced() {
        CompanySegmentsResponse response = service.getSegments(CORP_CODE, 2021);

        assertThat(response.year()).isEqualTo(2021);
        verify(segmentRepository, never()).findLatestFiscalYear(anyString(), any());
        verify(segmentRepository).findSegmentChanges(CORP_CODE, 2021, 2020);
    }

    @Test
    @DisplayName("없는 기업은 COMPANY_NOT_FOUND 로 예외를 던진다")
    void unknownCompanyThrows() {
        given(companyRepository.existsById("00000000")).willReturn(false);

        assertThatThrownBy(() -> service.getSegments("00000000", null))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.COMPANY_NOT_FOUND);
    }

    private static SegmentChangeProjection segment(String code, String revenue,
                                                   Integer employees, Integer prevEmployees) {
        SegmentChangeProjection projection = mock(SegmentChangeProjection.class);
        given(projection.getSegmentCode()).willReturn(code);
        given(projection.getRevenue()).willReturn(revenue == null ? null : new BigDecimal(revenue));
        given(projection.getEmployeeCount()).willReturn(employees);
        given(projection.getPrevEmployeeCount()).willReturn(prevEmployees);
        return projection;
    }

    private static MetricValueProjection metric(String value, String prevValue) {
        MetricValueProjection projection = mock(MetricValueProjection.class);
        given(projection.getValue()).willReturn(value == null ? null : new BigDecimal(value));
        given(projection.getPrevValue()).willReturn(prevValue == null ? null : new BigDecimal(prevValue));
        return projection;
    }
}

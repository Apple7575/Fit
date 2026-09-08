package com.ssafy.companyanalysis.company.service;

import com.ssafy.companyanalysis.company.dto.CompanyProfileResponse;
import com.ssafy.companyanalysis.company.repository.CompanyProfileRepository;
import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.company.repository.ProfileSegmentProjection;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

/**
 * 기준연도 결정과 파생값 계산처럼 DB 없이 확정할 수 있는 부분을 검증한다.
 *
 * <p>부문 매출은 아직 적재되지 않았지만(S15P21A504-73), 합계·비중 규칙은 값이 들어오기
 * 전에 고정해 두어야 나중에 값만 바뀌었을 때 계산이 달라지지 않는다.
 */
class CompanyProfileServiceTest {

    private static final String CORP_CODE = "00126380";

    private CompanyRepository companyRepository;
    private CompanyProfileRepository companyProfileRepository;
    private CompanyProfileService service;

    @BeforeEach
    void setUp() {
        companyRepository = mock(CompanyRepository.class);
        companyProfileRepository = mock(CompanyProfileRepository.class);
        service = new CompanyProfileService(companyRepository, companyProfileRepository);

        given(companyRepository.existsById(CORP_CODE)).willReturn(true);
    }

    @Test
    @DisplayName("부문 매출에서 합계와 비중을 계산해 응답에 싣는다")
    void computesTotalRevenueAndShares() {
        given(companyProfileRepository.findLatestFiscalYear(CORP_CODE)).willReturn(2025);
        given(companyProfileRepository.findBusinessNames(CORP_CODE, 2025))
                .willReturn(List.of("반도체", "스마트폰", "가전"));
        given(companyProfileRepository.findProductNames(CORP_CODE, 2025))
                .willReturn(List.of("HBM", "DRAM"));
        // 목을 만드는 것도 스터빙이라 바깥 given(...) 안에서 만들면 스터빙이 겹친다.
        List<ProfileSegmentProjection> rows =
                List.of(segment("DS", "232000000000000"), segment("DX", "168000000000000"));
        given(companyProfileRepository.findSegments(CORP_CODE, 2025)).willReturn(rows);

        CompanyProfileResponse response = service.getProfile(CORP_CODE, null);

        assertThat(response.year()).isEqualTo(2025);
        assertThat(response.businesses()).containsExactly("반도체", "스마트폰", "가전");
        assertThat(response.products()).containsExactly("HBM", "DRAM");
        // 부문 단순합. 명세가 그렇게 정의했다.
        assertThat(response.totalRevenue()).isEqualByComparingTo("400000000000000");
        assertThat(response.segments()).extracting(CompanyProfileResponse.Segment::code)
                .containsExactly("DS", "DX");
        assertThat(response.segments().get(0).revenueShare()).isEqualByComparingTo("58.0");
        assertThat(response.segments().get(1).revenueShare()).isEqualByComparingTo("42.0");
    }

    @Test
    @DisplayName("매출을 공시하지 않은 부문은 목록에 남고 매출·비중만 null 이다")
    void undisclosedSegmentKeepsItsSlot() {
        given(companyProfileRepository.findLatestFiscalYear(CORP_CODE)).willReturn(2025);
        List<ProfileSegmentProjection> rows =
                List.of(segment("DS", "232000000000000"), segment("SDC", null));
        given(companyProfileRepository.findSegments(CORP_CODE, 2025)).willReturn(rows);

        CompanyProfileResponse response = service.getProfile(CORP_CODE, null);

        assertThat(response.segments()).hasSize(2);
        assertThat(response.segments().get(1).code()).isEqualTo("SDC");
        assertThat(response.segments().get(1).revenue()).isNull();
        assertThat(response.segments().get(1).revenueShare()).isNull();
        // 미공시 부문은 합계에도 들어가지 않는다. 그래서 비중의 합이 100 이 아니다.
        assertThat(response.totalRevenue()).isEqualByComparingTo("232000000000000");
        assertThat(response.segments().get(0).revenueShare()).isEqualByComparingTo("100.0");
    }

    @Test
    @DisplayName("매출을 공시한 부문이 하나도 없으면 합계는 0 이 아니라 null 이다")
    void totalRevenueIsNullNotZeroWhenNothingDisclosed() {
        given(companyProfileRepository.findLatestFiscalYear(CORP_CODE)).willReturn(2025);
        List<ProfileSegmentProjection> rows = List.of(segment("DS", null), segment("DX", null));
        given(companyProfileRepository.findSegments(CORP_CODE, 2025)).willReturn(rows);

        CompanyProfileResponse response = service.getProfile(CORP_CODE, null);

        assertThat(response.totalRevenue()).isNull();
        assertThat(response.segments()).allSatisfy(s -> assertThat(s.revenueShare()).isNull());
    }

    @Test
    @DisplayName("부문 매출 합계가 0 이면 비중을 계산하지 않는다 (분모 0)")
    void zeroTotalRevenueYieldsNullShare() {
        given(companyProfileRepository.findLatestFiscalYear(CORP_CODE)).willReturn(2025);
        List<ProfileSegmentProjection> rows = List.of(segment("DS", "0"));
        given(companyProfileRepository.findSegments(CORP_CODE, 2025)).willReturn(rows);

        CompanyProfileResponse response = service.getProfile(CORP_CODE, null);

        // 합계 자체는 사실이므로 0 을 그대로 싣는다. 나눌 수 없는 비중만 null 이다.
        assertThat(response.totalRevenue()).isEqualByComparingTo("0");
        assertThat(response.segments().get(0).revenueShare()).isNull();
    }

    @Test
    @DisplayName("연도를 주지 않으면 개요가 적재된 최신 연도를 쓴다")
    void resolvesLatestProfileYearWhenYearOmitted() {
        given(companyProfileRepository.findLatestFiscalYear(CORP_CODE)).willReturn(2024);

        assertThat(service.getProfile(CORP_CODE, null).year()).isEqualTo(2024);
        verify(companyProfileRepository).findBusinessNames(CORP_CODE, 2024);
    }

    @Test
    @DisplayName("개요가 한 해도 적재되지 않으면 year 는 null 이고 목록은 빈 배열이다")
    void emptyProfileWhenNothingLoaded() {
        given(companyProfileRepository.findLatestFiscalYear(CORP_CODE)).willReturn(null);

        CompanyProfileResponse response = service.getProfile(CORP_CODE, null);

        assertThat(response.year()).isNull();
        assertThat(response.businesses()).isEmpty();
        assertThat(response.segments()).isEmpty();
        assertThat(response.products()).isEmpty();
        assertThat(response.totalRevenue()).isNull();
        // 조회할 연도가 없으면 테이블을 읽지 않는다.
        verify(companyProfileRepository, never()).findSegments(anyString(), anyInt());
    }

    @Test
    @DisplayName("요청한 연도에 개요가 없어도 최신 연도로 갈아타지 않는다")
    void requestedYearIsNotSilentlyReplaced() {
        given(companyProfileRepository.findBusinessNames(CORP_CODE, 2021)).willReturn(List.of());
        given(companyProfileRepository.findProductNames(CORP_CODE, 2021)).willReturn(List.of());
        given(companyProfileRepository.findSegments(CORP_CODE, 2021)).willReturn(List.of());

        CompanyProfileResponse response = service.getProfile(CORP_CODE, 2021);

        assertThat(response.year()).isEqualTo(2021);
        assertThat(response.businesses()).isEmpty();
        assertThat(response.totalRevenue()).isNull();
        verify(companyProfileRepository, never()).findLatestFiscalYear(anyString());
    }

    @Test
    @DisplayName("없는 기업은 COMPANY_NOT_FOUND 로 예외를 던진다")
    void unknownCompanyThrows() {
        given(companyRepository.existsById("00000000")).willReturn(false);

        assertThatThrownBy(() -> service.getProfile("00000000", null))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.COMPANY_NOT_FOUND);
    }

    /** 부문 한 행. revenue 가 null 이면 매출 미공시다. */
    private static ProfileSegmentProjection segment(String code, String revenue) {
        ProfileSegmentProjection projection = mock(ProfileSegmentProjection.class);
        given(projection.getSegmentCode()).willReturn(code);
        given(projection.getRevenue()).willReturn(revenue == null ? null : new BigDecimal(revenue));
        return projection;
    }
}

package com.ssafy.companyanalysis.focus.service;

import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.focus.dto.CompanyFocusResponse;
import com.ssafy.companyanalysis.focus.repository.CompanyFocusRepository;
import com.ssafy.companyanalysis.focus.repository.FocusDirectionItemProjection;
import com.ssafy.companyanalysis.focus.repository.FocusDirectionProjection;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.metric.repository.MetricRepository;
import com.ssafy.companyanalysis.metric.repository.MetricValueProjection;
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
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

/**
 * 기준연도 결정과 R&D 증가율 계산처럼 DB 없이 확정할 수 있는 부분을 검증한다.
 *
 * <p>사업 방향은 AI 분석이, R&D 수치는 지표 적재가 있어야 채워진다. 둘의 진행이 다르므로
 * 한쪽만 있을 때 응답이 어떻게 되는지가 이 테스트의 관심사다.
 */
class CompanyFocusServiceTest {

    private static final String CORP_CODE = "00126380";

    private CompanyRepository companyRepository;
    private CompanyFocusRepository companyFocusRepository;
    private MetricRepository metricRepository;
    private CompanyFocusService service;

    @BeforeEach
    void setUp() {
        companyRepository = mock(CompanyRepository.class);
        companyFocusRepository = mock(CompanyFocusRepository.class);
        metricRepository = mock(MetricRepository.class);
        service = new CompanyFocusService(companyRepository, companyFocusRepository, metricRepository);

        given(companyRepository.existsById(CORP_CODE)).willReturn(true);
    }

    @Test
    @DisplayName("사업 방향 목록을 구분값으로 나누고 R&D 증가율을 계산한다")
    void splitsDirectionItemsAndComputesGrowthRate() {
        given(companyFocusRepository.findLatestFiscalYear(eq(CORP_CODE), any())).willReturn(2025);
        List<FocusDirectionItemProjection> items = List.of(
                item("KEYWORD", "온디바이스 AI"),
                item("NEW_BUSINESS", "파운드리"),
                item("NEW_BUSINESS", "로봇"));
        given(companyFocusRepository.findDirectionItems(CORP_CODE, 2025)).willReturn(items);
        FocusDirectionProjection projection = direction("주력을 메모리에서 파운드리로 옮기고 있다");
        given(companyFocusRepository.findDirection(CORP_CODE, 2025)).willReturn(Optional.of(projection));
        given(companyFocusRepository.findRndFields(CORP_CODE, 2025)).willReturn(List.of("HBM", "GAA"));
        List<MetricValueProjection> metrics = List.of(
                metric("rd_cost", 0, "37000000000000", "34000000000000"),
                metric("rd_ratio", 1, "9.3", "8.8"));
        given(metricRepository.findMetricValues(CORP_CODE, List.of("rd_cost", "rd_ratio"), 2025, 2024))
                .willReturn(metrics);

        CompanyFocusResponse response = service.getFocus(CORP_CODE, null);

        assertThat(response.year()).isEqualTo(2025);
        // 쿼리가 구분값·순서로 정렬해 오므로 걸러내면 순서가 유지된다.
        assertThat(response.direction().newBusiness()).containsExactly("파운드리", "로봇");
        assertThat(response.direction().keywords()).containsExactly("온디바이스 AI");
        assertThat(response.direction().strategyChange()).isEqualTo("주력을 메모리에서 파운드리로 옮기고 있다");
        assertThat(response.rnd().expense()).isEqualByComparingTo("37000000000000");
        assertThat(response.rnd().growthRate()).isEqualByComparingTo("8.8");
        assertThat(response.rnd().revenueRatio()).isEqualByComparingTo("9.3");
        assertThat(response.rnd().fields()).containsExactly("HBM", "GAA");
    }

    @Test
    @DisplayName("R&D 만 적재된 기업도 200 이고 사업 방향은 빈 골격으로 나간다")
    void rndOnlyCompanyStillReturnsDirectionSkeleton() {
        given(companyFocusRepository.findLatestFiscalYear(eq(CORP_CODE), any())).willReturn(2025);
        given(companyFocusRepository.findDirectionItems(CORP_CODE, 2025)).willReturn(List.of());
        given(companyFocusRepository.findDirection(CORP_CODE, 2025)).willReturn(Optional.empty());
        given(companyFocusRepository.findRndFields(CORP_CODE, 2025)).willReturn(List.of());
        List<MetricValueProjection> metrics = List.of(metric("rd_cost", 0, "37000000000000", null));
        given(metricRepository.findMetricValues(eq(CORP_CODE), any(), eq(2025), eq(2024)))
                .willReturn(metrics);

        CompanyFocusResponse response = service.getFocus(CORP_CODE, null);

        assertThat(response.direction().newBusiness()).isEmpty();
        assertThat(response.direction().keywords()).isEmpty();
        assertThat(response.direction().strategyChange()).isNull();
        assertThat(response.rnd().expense()).isEqualByComparingTo("37000000000000");
        // 전년 비용이 없으면 증가율만 못 낸다. 금액은 그대로 싣는다.
        assertThat(response.rnd().growthRate()).isNull();
        assertThat(response.rnd().revenueRatio()).isNull();
    }

    @Test
    @DisplayName("전년 R&D 비용이 0 이면 증가율을 계산하지 않는다")
    void zeroPreviousCostYieldsNullGrowthRate() {
        given(companyFocusRepository.findLatestFiscalYear(eq(CORP_CODE), any())).willReturn(2025);
        List<MetricValueProjection> metrics = List.of(metric("rd_cost", 0, "1000000", "0"));
        given(metricRepository.findMetricValues(eq(CORP_CODE), any(), eq(2025), eq(2024)))
                .willReturn(metrics);

        assertThat(service.getFocus(CORP_CODE, null).rnd().growthRate()).isNull();
    }

    @Test
    @DisplayName("금액은 카탈로그 자릿수로 맞춰 나간다 (NUMERIC 소수 자리 제거)")
    void amountsUseCatalogScale() {
        given(companyFocusRepository.findLatestFiscalYear(eq(CORP_CODE), any())).willReturn(2025);
        List<MetricValueProjection> metrics = List.of(
                metric("rd_cost", 0, "37000000000000.0000", null),
                metric("rd_ratio", 1, "9.2500", null));
        given(metricRepository.findMetricValues(eq(CORP_CODE), any(), eq(2025), eq(2024)))
                .willReturn(metrics);

        CompanyFocusResponse.Rnd rnd = service.getFocus(CORP_CODE, null).rnd();

        assertThat(rnd.expense().scale()).isZero();
        assertThat(rnd.revenueRatio()).isEqualByComparingTo("9.3");
    }

    @Test
    @DisplayName("사업 방향 행은 있는데 전략 변화만 비어 있으면 그 값만 null 이다")
    void presentDirectionRowWithNullStrategy() {
        given(companyFocusRepository.findLatestFiscalYear(eq(CORP_CODE), any())).willReturn(2025);
        // 목을 만드는 것도 스터빙이라 바깥 given(...) 안에서 만들면 스터빙이 겹친다.
        List<FocusDirectionItemProjection> items = List.of(item("KEYWORD", "AI"));
        given(companyFocusRepository.findDirectionItems(CORP_CODE, 2025)).willReturn(items);
        FocusDirectionProjection projection = direction(null);
        given(companyFocusRepository.findDirection(CORP_CODE, 2025)).willReturn(Optional.of(projection));

        CompanyFocusResponse response = service.getFocus(CORP_CODE, null);

        assertThat(response.direction().strategyChange()).isNull();
        assertThat(response.direction().keywords()).containsExactly("AI");
    }

    @Test
    @DisplayName("집중 분야 데이터가 한 해도 없으면 year 는 null 이고 두 블록은 빈 골격이다")
    void emptyFocusWhenNothingLoaded() {
        given(companyFocusRepository.findLatestFiscalYear(eq(CORP_CODE), any())).willReturn(null);

        CompanyFocusResponse response = service.getFocus(CORP_CODE, null);

        assertThat(response.year()).isNull();
        assertThat(response.direction().newBusiness()).isEmpty();
        assertThat(response.direction().keywords()).isEmpty();
        assertThat(response.direction().strategyChange()).isNull();
        assertThat(response.rnd().expense()).isNull();
        assertThat(response.rnd().growthRate()).isNull();
        assertThat(response.rnd().revenueRatio()).isNull();
        assertThat(response.rnd().fields()).isEmpty();
        // 조회할 연도가 없으면 테이블도 지표도 읽지 않는다.
        verify(companyFocusRepository, never()).findDirectionItems(anyString(), anyInt());
        verify(metricRepository, never()).findMetricValues(anyString(), any(), anyInt(), anyInt());
    }

    @Test
    @DisplayName("요청한 연도에 데이터가 없어도 최신 연도로 갈아타지 않는다")
    void requestedYearIsNotSilentlyReplaced() {
        CompanyFocusResponse response = service.getFocus(CORP_CODE, 2021);

        assertThat(response.year()).isEqualTo(2021);
        verify(companyFocusRepository, never()).findLatestFiscalYear(anyString(), any());
        verify(companyFocusRepository).findDirectionItems(CORP_CODE, 2021);
    }

    @Test
    @DisplayName("없는 기업은 COMPANY_NOT_FOUND 로 예외를 던진다")
    void unknownCompanyThrows() {
        given(companyRepository.existsById("00000000")).willReturn(false);

        assertThatThrownBy(() -> service.getFocus("00000000", null))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.COMPANY_NOT_FOUND);
    }

    private static FocusDirectionItemProjection item(String type, String name) {
        FocusDirectionItemProjection projection = mock(FocusDirectionItemProjection.class);
        given(projection.getItemType()).willReturn(type);
        given(projection.getItemName()).willReturn(name);
        return projection;
    }

    private static FocusDirectionProjection direction(String strategyChange) {
        FocusDirectionProjection projection = mock(FocusDirectionProjection.class);
        given(projection.getStrategyChange()).willReturn(strategyChange);
        return projection;
    }

    private static MetricValueProjection metric(String code, int scale, String value, String prevValue) {
        MetricValueProjection projection = mock(MetricValueProjection.class);
        given(projection.getMetricCode()).willReturn(code);
        given(projection.getValueScale()).willReturn((short) scale);
        given(projection.getValue()).willReturn(value == null ? null : new BigDecimal(value));
        given(projection.getPrevValue()).willReturn(prevValue == null ? null : new BigDecimal(prevValue));
        return projection;
    }
}

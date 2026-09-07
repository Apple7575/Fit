package com.ssafy.companyanalysis.focus.service;

import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.focus.dto.CompanyActivitiesResponse;
import com.ssafy.companyanalysis.focus.repository.ActivityProjection;
import com.ssafy.companyanalysis.focus.repository.CompanyActivityRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

/** 유형 검증과 구간 검증, 프로젝션 매핑을 검증한다. */
class CompanyActivityServiceTest {

    private static final String CORP_CODE = "00126380";

    private CompanyRepository companyRepository;
    private CompanyActivityRepository activityRepository;
    private CompanyActivityService service;

    @BeforeEach
    void setUp() {
        companyRepository = mock(CompanyRepository.class);
        activityRepository = mock(CompanyActivityRepository.class);
        service = new CompanyActivityService(companyRepository, activityRepository);

        given(companyRepository.existsById(CORP_CODE)).willReturn(true);
    }

    @Test
    @DisplayName("이벤트를 응답 항목으로 그대로 옮긴다")
    void mapsProjectionsToItems() {
        List<ActivityProjection> rows = List.of(
                activity(2025, "facility", "파운드리", "미국 테일러 공장 생산능력 확대", "23000000000000"),
                activity(2024, "facility", "HBM", "평택 P4 라인 증설", null));
        given(activityRepository.findActivities(CORP_CODE, "facility", null, null)).willReturn(rows);

        CompanyActivitiesResponse response = service.getActivities(CORP_CODE, "facility", null, null);

        assertThat(response.items()).hasSize(2);
        assertThat(response.items().get(0).year()).isEqualTo(2025);
        assertThat(response.items().get(0).type()).isEqualTo("facility");
        assertThat(response.items().get(0).field()).isEqualTo("파운드리");
        assertThat(response.items().get(0).amount()).isEqualByComparingTo("23000000000000");
        // 금액을 공시하지 않은 건도 목록에 남는다. 0 으로 채우지 않는다.
        assertThat(response.items().get(1).amount()).isNull();
    }

    @Test
    @DisplayName("이벤트가 없으면 오류가 아니라 빈 배열이다")
    void emptyResultIsNotAnError() {
        given(activityRepository.findActivities(CORP_CODE, "ma", null, null)).willReturn(List.of());

        assertThat(service.getActivities(CORP_CODE, "ma", null, null).items()).isEmpty();
    }

    @Test
    @DisplayName("from/to 를 그대로 조회에 넘긴다")
    void passesRangeThrough() {
        service.getActivities(CORP_CODE, "transfer", 2021, 2025);

        verify(activityRepository).findActivities(CORP_CODE, "transfer", 2021, 2025);
    }

    @Test
    @DisplayName("모르는 유형은 조용히 걸러내지 않고 400 INVALID_PARAMETER 다")
    void unknownTypeIsBadRequest() {
        assertThatThrownBy(() -> service.getActivities(CORP_CODE, "buyback", null, null))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.INVALID_PARAMETER);

        verify(activityRepository, never()).findActivities(anyString(), anyString(), any(), any());
    }

    @Test
    @DisplayName("명세의 네 유형은 모두 통과한다")
    void allSpecifiedTypesAreAccepted() {
        for (String type : List.of("facility", "corporate_invest", "ma", "transfer")) {
            assertThat(service.getActivities(CORP_CODE, type, null, null).items()).isEmpty();
        }
    }

    @Test
    @DisplayName("from 이 to 보다 크면 400 INVALID_PARAMETER 다")
    void reversedRangeIsBadRequest() {
        assertThatThrownBy(() -> service.getActivities(CORP_CODE, "facility", 2025, 2021))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.INVALID_PARAMETER);
    }

    @Test
    @DisplayName("한쪽만 준 구간은 유효하다")
    void openEndedRangeIsAllowed() {
        service.getActivities(CORP_CODE, "facility", 2023, null);

        verify(activityRepository).findActivities(CORP_CODE, "facility", 2023, null);
    }

    @Test
    @DisplayName("없는 기업은 유형 검증보다 먼저 COMPANY_NOT_FOUND 다")
    void unknownCompanyThrowsBeforeTypeCheck() {
        given(companyRepository.existsById("00000000")).willReturn(false);

        assertThatThrownBy(() -> service.getActivities("00000000", "buyback", null, null))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.COMPANY_NOT_FOUND);
    }

    private static ActivityProjection activity(int year, String type, String field,
                                               String purpose, String amount) {
        ActivityProjection p = mock(ActivityProjection.class);
        given(p.getYear()).willReturn(year);
        given(p.getType()).willReturn(type);
        given(p.getField()).willReturn(field);
        given(p.getPurpose()).willReturn(purpose);
        given(p.getAmount()).willReturn(amount == null ? null : new BigDecimal(amount));
        return p;
    }
}

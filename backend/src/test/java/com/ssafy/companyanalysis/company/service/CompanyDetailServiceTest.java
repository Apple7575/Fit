package com.ssafy.companyanalysis.company.service;

import com.ssafy.companyanalysis.company.dto.CompanyDetailResponse;
import com.ssafy.companyanalysis.company.repository.CompanyDetailProjection;
import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

/**
 * 프로젝션 매핑과 404 처리처럼 DB 없이 확정할 수 있는 부분을 검증한다.
 */
class CompanyDetailServiceTest {

    private static final String CORP_CODE = "00164779";

    private CompanyRepository companyRepository;
    private CompanyDetailService service;

    @BeforeEach
    void setUp() {
        companyRepository = mock(CompanyRepository.class);
        service = new CompanyDetailService(companyRepository);
    }

    @Test
    @DisplayName("헤더 조회는 프로젝션을 응답 DTO 로 그대로 옮긴다")
    void mapsProjectionToResponse() {
        // 목을 만드는 것도 스터빙이라 바깥 given(...) 안에서 만들면 스터빙이 겹친다.
        CompanyDetailProjection p = projection();
        given(companyRepository.findDetailByCorpCode(CORP_CODE)).willReturn(Optional.of(p));

        CompanyDetailResponse response = service.getCompany(CORP_CODE);

        assertThat(response.corpCode()).isEqualTo(CORP_CODE);
        assertThat(response.corpName()).isEqualTo("SK하이닉스");
        assertThat(response.industryCode()).isEqualTo("26");
        assertThat(response.ceo()).isEqualTo("곽노정");
        assertThat(response.establishedDate()).isEqualTo(LocalDate.of(1949, 10, 15));
        assertThat(response.address()).isEqualTo("경기도 이천시 부발읍 경충대로 2091");
        assertThat(response.homepageUrl()).isEqualTo("https://www.skhynix.com");
        assertThat(response.dataYear()).isEqualTo(2025);
    }

    @Test
    @DisplayName("적재된 지표가 하나도 없으면 dataYear 는 null 이다")
    void nullDataYearWhenNothingLoaded() {
        CompanyDetailProjection p = projection();
        given(p.getDataYear()).willReturn(null);
        given(companyRepository.findDetailByCorpCode(CORP_CODE)).willReturn(Optional.of(p));

        assertThat(service.getCompany(CORP_CODE).dataYear()).isNull();
    }

    @Test
    @DisplayName("주소·홈페이지가 아직 적재되지 않았어도 오류가 아니라 null 로 나간다")
    void nullAddressAndHomepageAreNotAnError() {
        CompanyDetailProjection p = projection();
        given(p.getAddress()).willReturn(null);
        given(p.getHomepageUrl()).willReturn(null);
        given(companyRepository.findDetailByCorpCode(CORP_CODE)).willReturn(Optional.of(p));

        CompanyDetailResponse response = service.getCompany(CORP_CODE);

        assertThat(response.address()).isNull();
        assertThat(response.homepageUrl()).isNull();
        assertThat(response.corpName()).isEqualTo("SK하이닉스");
    }

    @Test
    @DisplayName("없는 기업은 COMPANY_NOT_FOUND 로 예외를 던진다")
    void unknownCompanyThrows() {
        given(companyRepository.findDetailByCorpCode("00000000"))
                .willReturn(Optional.empty());

        assertThatThrownBy(() -> service.getCompany("00000000"))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.COMPANY_NOT_FOUND);
    }

    private CompanyDetailProjection projection() {
        CompanyDetailProjection p = mock(CompanyDetailProjection.class);
        given(p.getCorpCode()).willReturn(CORP_CODE);
        given(p.getCorpName()).willReturn("SK하이닉스");
        given(p.getIndustryCode()).willReturn("26");
        given(p.getIndustryName()).willReturn("전자 부품, 컴퓨터, 영상, 음향 및 통신장비 제조업");
        given(p.getCeoNm()).willReturn("곽노정");
        given(p.getEstablishedDate()).willReturn(LocalDate.of(1949, 10, 15));
        given(p.getAddress()).willReturn("경기도 이천시 부발읍 경충대로 2091");
        given(p.getHomepageUrl()).willReturn("https://www.skhynix.com");
        given(p.getDataYear()).willReturn(2025);
        return p;
    }
}

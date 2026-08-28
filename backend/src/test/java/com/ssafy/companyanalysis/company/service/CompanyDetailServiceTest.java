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
 * corp_cls → market 파생과 404 처리처럼 DB 없이 확정할 수 있는 부분을 검증한다.
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
    @DisplayName("상세 조회는 프로젝션을 응답 DTO 로 옮기고 corp_cls 를 KOSPI 로 파생한다")
    void mapsProjectionAndDerivesMarket() {
        CompanyDetailProjection p = projection("Y");
        given(companyRepository.findDetailByCorpCode(CORP_CODE)).willReturn(Optional.of(p));

        CompanyDetailResponse response = service.getCompany(CORP_CODE);

        assertThat(response.corpCode()).isEqualTo(CORP_CODE);
        assertThat(response.corpName()).isEqualTo("SK하이닉스");
        assertThat(response.industryCode()).isEqualTo("26");
        assertThat(response.market()).isEqualTo("KOSPI");
        assertThat(response.ceo()).isEqualTo("곽노정");
        assertThat(response.establishedDate()).isEqualTo(LocalDate.of(1949, 10, 15));
    }

    @Test
    @DisplayName("corp_cls K·N 은 각각 KOSDAQ·KONEX 로, 기타(E)·null 은 null 로 파생한다")
    void derivesMarketForEachCorpCls() {
        assertThat(marketOf("K")).isEqualTo("KOSDAQ");
        assertThat(marketOf("N")).isEqualTo("KONEX");
        assertThat(marketOf("E")).isNull();
        assertThat(marketOf(null)).isNull();
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

    private String marketOf(String corpCls) {
        CompanyDetailProjection p = projection(corpCls);
        given(companyRepository.findDetailByCorpCode(CORP_CODE)).willReturn(Optional.of(p));
        return service.getCompany(CORP_CODE).market();
    }

    private CompanyDetailProjection projection(String corpCls) {
        CompanyDetailProjection p = mock(CompanyDetailProjection.class);
        given(p.getCorpCode()).willReturn(CORP_CODE);
        given(p.getCorpName()).willReturn("SK하이닉스");
        given(p.getStockCode()).willReturn("000660");
        given(p.getIndustryCode()).willReturn("26");
        given(p.getIndustryName()).willReturn("전자 부품, 컴퓨터, 영상, 음향 및 통신장비 제조업");
        given(p.getCorpCls()).willReturn(corpCls);
        given(p.getCeoNm()).willReturn("곽노정");
        given(p.getEstablishedDate()).willReturn(LocalDate.of(1949, 10, 15));
        return p;
    }
}

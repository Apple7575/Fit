package com.ssafy.companyanalysis.company.service;

import com.ssafy.companyanalysis.company.dto.CompanyDetailResponse;
import com.ssafy.companyanalysis.company.repository.CompanyDetailProjection;
import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CompanyDetailService {

    private final CompanyRepository companyRepository;

    public CompanyDetailService(CompanyRepository companyRepository) {
        this.companyRepository = companyRepository;
    }

    /**
     * corpCode 로 기업 헤더 정보를 조회한다. 없으면 404 COMPANY_NOT_FOUND 다.
     * corpCode 형식이 어긋나도 조회에 실패할 뿐이므로 같은 404 로 통일한다(명세에 400 없음).
     *
     * <p>v2 에서 corp_cls 를 market 으로 바꾸던 변환이 사라졌다. 응답이 그 필드를 더 이상
     * 싣지 않으므로 프로젝션을 그대로 옮기기만 한다.
     */
    @Transactional(readOnly = true)
    public CompanyDetailResponse getCompany(String corpCode) {
        CompanyDetailProjection projection = companyRepository.findDetailByCorpCode(corpCode)
                .orElseThrow(() -> new BusinessException(ErrorCode.COMPANY_NOT_FOUND));

        return new CompanyDetailResponse(
                projection.getCorpCode(),
                projection.getCorpName(),
                projection.getIndustryCode(),
                projection.getIndustryName(),
                projection.getCeoNm(),
                projection.getEstablishedDate(),
                projection.getAddress(),
                projection.getHomepageUrl(),
                projection.getDataYear());
    }
}

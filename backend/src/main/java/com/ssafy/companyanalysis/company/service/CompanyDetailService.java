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
     * corpCode 로 기업 상세를 조회한다. 없으면 404 COMPANY_NOT_FOUND 다.
     * corpCode 형식이 어긋나도 조회에 실패할 뿐이므로 같은 404 로 통일한다(명세에 400 없음).
     */
    @Transactional(readOnly = true)
    public CompanyDetailResponse getCompany(String corpCode) {
        CompanyDetailProjection p = companyRepository.findDetailByCorpCode(corpCode)
                .orElseThrow(() -> new BusinessException(ErrorCode.COMPANY_NOT_FOUND));

        return new CompanyDetailResponse(
                p.getCorpCode(),
                p.getCorpName(),
                p.getStockCode(),
                p.getIndustryCode(),
                p.getIndustryName(),
                toMarket(p.getCorpCls()),
                p.getCeoNm(),
                p.getEstablishedDate());
    }

    /** corp_cls 를 명세의 market 값으로 바꾼다. 기타(E)·미분류는 세 시장에 없어 null 이다. */
    private static String toMarket(String corpCls) {
        if (corpCls == null) {
            return null;
        }
        return switch (corpCls) {
            case "Y" -> "KOSPI";
            case "K" -> "KOSDAQ";
            case "N" -> "KONEX";
            default -> null;
        };
    }
}

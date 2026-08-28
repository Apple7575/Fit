package com.ssafy.companyanalysis.company.service;

import com.ssafy.companyanalysis.company.dto.CompanySearchResponse;
import com.ssafy.companyanalysis.company.dto.CompanySummaryResponse;
import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.company.repository.CompanySummaryProjection;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class CompanySearchService {

    private final CompanyRepository companyRepository;

    public CompanySearchService(CompanyRepository companyRepository) {
        this.companyRepository = companyRepository;
    }

    /**
     * 기업을 검색한다. 결과가 없는 것은 오류가 아니라 빈 배열이다.
     *
     * @param page 1부터 시작하는 페이지 번호. Pageable 은 0부터라 여기서 변환한다.
     */
    @Transactional(readOnly = true)
    public CompanySearchResponse search(String keyword, int page, int size) {
        Page<CompanySummaryProjection> found =
                companyRepository.search(keyword.trim(), PageRequest.of(page - 1, size));

        List<CompanySummaryResponse> items = found.getContent().stream()
                .map(p -> new CompanySummaryResponse(
                        p.getCorpCode(),
                        p.getCorpName(),
                        p.getStockCode(),
                        p.getIndustryCode(),
                        p.getIndustryName()))
                .toList();

        return new CompanySearchResponse(items, found.getTotalElements());
    }
}

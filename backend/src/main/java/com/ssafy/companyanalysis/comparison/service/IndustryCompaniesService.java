package com.ssafy.companyanalysis.comparison.service;

import com.ssafy.companyanalysis.company.domain.Industry;
import com.ssafy.companyanalysis.comparison.dto.IndustryCompaniesResponse;
import com.ssafy.companyanalysis.comparison.repository.IndustryCompanyProjection;
import com.ssafy.companyanalysis.comparison.repository.IndustryCompanyRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.metric.domain.Metric;
import com.ssafy.companyanalysis.metric.repository.MetricRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;

@Service
public class IndustryCompaniesService {

    /** 명세가 정한 기본 정렬. 규모가 가장 눈에 익은 축이라 후보 목록의 맨 위가 큰 기업이 된다. */
    public static final String DEFAULT_SORT = "revenue";

    private final IndustryCompanyRepository industryCompanyRepository;
    private final MetricRepository metricRepository;

    public IndustryCompaniesService(IndustryCompanyRepository industryCompanyRepository,
                                    MetricRepository metricRepository) {
        this.industryCompanyRepository = industryCompanyRepository;
        this.metricRepository = metricRepository;
    }

    /**
     * 같은 KSIC 중분류의 비교 후보 기업을 반환한다.
     *
     * <p>없는 industryCode 는 404 가 아니라 빈 목록의 200 이다. 명세가 그렇게 정했고,
     * 화면 쪽 사정도 같다 — 이 목록은 사용자가 무언가 누르기 전에 자동으로 불리므로
     * 산업이 아직 안 붙은 기업에서 404 를 내면 비교 화면 전체가 오류로 보인다.
     *
     * @param sort  정렬에 쓸 지표 슬러그. null 이면 {@link #DEFAULT_SORT}
     * @param limit 최대 반환 개수. 컨트롤러가 범위를 검증한다
     */
    @Transactional(readOnly = true)
    public IndustryCompaniesResponse listCandidates(String industryCode, String sort, int limit) {
        String sortMetric = resolveSort(sort);

        Optional<Industry> industry = industryCompanyRepository.findByIndustryCode(industryCode);
        if (industry.isEmpty()) {
            return new IndustryCompaniesResponse(null, List.of());
        }

        List<IndustryCompaniesResponse.Company> companies =
                industryCompanyRepository.findCandidates(industryCode, sortMetric, limit).stream()
                        .map(row -> new IndustryCompaniesResponse.Company(row.getCorpCode(), row.getCorpName()))
                        .toList();

        return new IndustryCompaniesResponse(
                new IndustryCompaniesResponse.Industry(
                        industry.get().getIndustryCode(), industry.get().getIndustryName()),
                companies);
    }

    /**
     * 정렬 지표를 검증한다. 카탈로그에서 {@code is_active} 인 지표만 받는다.
     *
     * <p>모르는 값에 METRIC_NOT_SUPPORTED 가 아니라 INVALID_PARAMETER 를 내는 것은
     * 명세가 이 엔드포인트의 에러로 400 INVALID_PARAMETER 하나만 정해 두었기 때문이다.
     * 지표 조회의 {@code keys} 는 "이 지표를 달라"는 요청이라 지표 코드로 답하는 게 맞지만,
     * 여기서 지표는 정렬 옵션이라 잘못된 값은 파라미터 오류로 본다.
     *
     * <p>기본값으로 조용히 되돌리지 않는 이유는, 호출자가 revenue 순으로 정렬됐다고 믿는
     * 상태와 실제 정렬이 달라지기 때문이다. 틀린 값은 틀렸다고 알려주는 편이 낫다.
     */
    private String resolveSort(String sort) {
        if (sort == null || sort.isBlank()) {
            return DEFAULT_SORT;
        }

        String requested = sort.trim();
        boolean supported = metricRepository.findByActiveTrueOrderByDisplayOrderAsc().stream()
                .map(Metric::getMetricCode)
                .anyMatch(requested::equals);

        if (!supported) {
            throw new BusinessException(ErrorCode.INVALID_PARAMETER, "정렬할 수 없는 지표입니다: " + requested);
        }
        return requested;
    }
}

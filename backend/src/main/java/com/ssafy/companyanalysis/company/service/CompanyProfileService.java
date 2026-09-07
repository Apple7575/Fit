package com.ssafy.companyanalysis.company.service;

import com.ssafy.companyanalysis.company.dto.CompanyProfileResponse;
import com.ssafy.companyanalysis.company.repository.CompanyProfileRepository;
import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.company.repository.ProfileSegmentProjection;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;

@Service
public class CompanyProfileService {

    private static final BigDecimal HUNDRED = BigDecimal.valueOf(100);

    /** 부문 비중 소수 자릿수. 지표 조회의 비율과 같은 1자리다(명세 예시가 58.0). */
    private static final int SHARE_SCALE = 1;

    private final CompanyRepository companyRepository;
    private final CompanyProfileRepository companyProfileRepository;

    public CompanyProfileService(CompanyRepository companyRepository,
                                 CompanyProfileRepository companyProfileRepository) {
        this.companyRepository = companyRepository;
        this.companyProfileRepository = companyProfileRepository;
    }

    /**
     * 기업 개요(주요 사업·사업부문 매출·주요 제품)를 조회한다. 없는 기업은 404 COMPANY_NOT_FOUND 다.
     *
     * <p>기업이 있는 한 개요가 하나도 없어도 200 이다. 사업보고서 추출은 재무 지표보다
     * 늦게 들어오므로, 데이터가 아직 없는 기업이 없는 기업처럼 보이면 안 된다
     * (docs/decisions/0001-missing-data-response.md 규칙 1).
     *
     * @param year 생략하면 이 기업의 개요가 적재된 최신 연도. 그것도 없으면 응답의 year 가 null
     */
    @Transactional(readOnly = true)
    public CompanyProfileResponse getProfile(String corpCode, Integer year) {
        requireCompany(corpCode);

        Integer targetYear = resolveYear(corpCode, year);
        if (targetYear == null) {
            // 이 기업의 개요가 한 해도 적재되지 않았다. 조회할 연도가 없을 뿐 오류는 아니므로
            // 골격만 내보낸다. 목록은 null 이 아니라 빈 배열이다(규칙 4).
            return new CompanyProfileResponse(null, List.of(), List.of(), null, List.of());
        }

        List<ProfileSegmentProjection> rows = companyProfileRepository.findSegments(corpCode, targetYear);
        BigDecimal totalRevenue = totalRevenue(rows);

        return new CompanyProfileResponse(
                targetYear,
                companyProfileRepository.findBusinessNames(corpCode, targetYear),
                toSegments(rows, totalRevenue),
                totalRevenue,
                companyProfileRepository.findProductNames(corpCode, targetYear));
    }

    private void requireCompany(String corpCode) {
        if (!companyRepository.existsById(corpCode)) {
            throw new BusinessException(ErrorCode.COMPANY_NOT_FOUND);
        }
    }

    /**
     * 요청 연도가 있으면 그대로, 없으면 개요의 최신 적재 연도. 둘 다 없으면 null.
     *
     * <p>요청한 연도에 개요가 없을 때 최신 연도로 갈아타지 않는다. 2023년을 물었는데
     * 2025년 개요가 오면 호출자는 자기가 받은 값이 어느 해인지 응답의 year 를 다시 읽어야
     * 알 수 있고, 그마저 놓치면 다른 해의 값을 비교하게 된다.
     */
    private Integer resolveYear(String corpCode, Integer year) {
        return year != null ? year : companyProfileRepository.findLatestFiscalYear(corpCode);
    }

    /**
     * 부문 매출의 단순합. 매출을 공시한 부문이 하나도 없으면 null 이다.
     *
     * <p>0 을 내보내지 않는다. 부문 매출이 모두 미공시인 것과 합계가 정말 0원인 것은 다른
     * 사실이고, 화면은 앞의 경우에 "정보 없음"을, 뒤의 경우에 0원을 보여야 한다(규칙 3).
     *
     * <p>명세가 이 값을 "부문 단순합"으로 정의했다. 지표 조회의 revenue 와 다른 값이며,
     * 미공시 부문이 빠져 있어 재무제표 매출액보다 작게 나오는 것이 정상이다.
     */
    private BigDecimal totalRevenue(List<ProfileSegmentProjection> rows) {
        return rows.stream()
                .map(ProfileSegmentProjection::getRevenue)
                .filter(revenue -> revenue != null)
                .reduce(BigDecimal::add)
                .orElse(null);
    }

    private List<CompanyProfileResponse.Segment> toSegments(List<ProfileSegmentProjection> rows,
                                                            BigDecimal totalRevenue) {
        return rows.stream()
                .map(row -> new CompanyProfileResponse.Segment(
                        row.getSegmentCode(), row.getRevenue(), share(row.getRevenue(), totalRevenue)))
                .toList();
    }

    /**
     * 부문 매출 비중(%). 부문 매출이 없거나 합계가 0 이하면 null 이다.
     *
     * <p>합계가 0 이하일 때 계산하지 않는 것은 지표 조회의 비율과 같은 이유다. 분모가
     * 0 이면 나눌 수 없고, 음수면 부호가 뒤집혀 적자 부문이 큰 비중처럼 보인다.
     *
     * <p>비중의 합이 100 이 안 될 수 있다. 미공시 부문은 분자가 없어 비중도 null 이고,
     * 그 부문의 몫은 어디에도 실리지 않는다. 화면에서 막대를 채울 때 감안해야 한다.
     */
    private BigDecimal share(BigDecimal revenue, BigDecimal totalRevenue) {
        if (revenue == null || totalRevenue == null || totalRevenue.signum() <= 0) {
            return null;
        }
        return revenue.multiply(HUNDRED).divide(totalRevenue, SHARE_SCALE, RoundingMode.HALF_UP);
    }
}

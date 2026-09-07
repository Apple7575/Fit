package com.ssafy.companyanalysis.focus.service;

import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.focus.dto.CompanySegmentsResponse;
import com.ssafy.companyanalysis.focus.repository.CompanySegmentChangeRepository;
import com.ssafy.companyanalysis.focus.repository.SegmentChangeProjection;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.metric.repository.MetricRepository;
import com.ssafy.companyanalysis.metric.repository.MetricValueProjection;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;

@Service
public class CompanySegmentsService {

    private static final BigDecimal HUNDRED = BigDecimal.valueOf(100);

    /** 부문 비중 소수 자릿수. 기업 개요의 비중과 같은 1자리다. */
    private static final int SHARE_SCALE = 1;

    /** 전사 직원 순증감의 원본 지표. */
    private static final String EMPLOYEE_COUNT = "employee_count";
    private static final List<String> TOTAL_METRICS = List.of(EMPLOYEE_COUNT);

    private final CompanyRepository companyRepository;
    private final CompanySegmentChangeRepository companySegmentChangeRepository;
    private final MetricRepository metricRepository;

    public CompanySegmentsService(CompanyRepository companyRepository,
                                  CompanySegmentChangeRepository companySegmentChangeRepository,
                                  MetricRepository metricRepository) {
        this.companyRepository = companyRepository;
        this.companySegmentChangeRepository = companySegmentChangeRepository;
        this.metricRepository = metricRepository;
    }

    /**
     * 사업부별 매출·인력 증감을 조회한다. 없는 기업은 404 COMPANY_NOT_FOUND 다.
     *
     * <p>부문 공시가 없어도 200 이다. 전사 직원 수만 적재된 기업은 부문 목록이 비고
     * {@code employeeTotalChange} 만 채워진다 — 그것도 화면이 보여줄 수 있는 사실이다.
     *
     * @param year 생략하면 이 기업의 부문·직원 데이터가 있는 최신 연도
     */
    @Transactional(readOnly = true)
    public CompanySegmentsResponse getSegments(String corpCode, Integer year) {
        requireCompany(corpCode);

        Integer targetYear = resolveYear(corpCode, year);
        if (targetYear == null) {
            // 부문도 직원 수도 한 해도 없다. 목록은 null 이 아니라 빈 배열이다.
            return new CompanySegmentsResponse(null, null, List.of());
        }

        List<SegmentChangeProjection> rows =
                companySegmentChangeRepository.findSegmentChanges(corpCode, targetYear, targetYear - 1);

        return new CompanySegmentsResponse(
                targetYear,
                employeeTotalChange(corpCode, targetYear),
                toSegments(rows, totalRevenue(rows)));
    }

    private void requireCompany(String corpCode) {
        if (!companyRepository.existsById(corpCode)) {
            throw new BusinessException(ErrorCode.COMPANY_NOT_FOUND);
        }
    }

    /** 요청 연도가 있으면 그대로, 없으면 부문·직원 데이터의 최신 연도. 둘 다 없으면 null. */
    private Integer resolveYear(String corpCode, Integer year) {
        return year != null
                ? year
                : companySegmentChangeRepository.findLatestFiscalYear(corpCode, TOTAL_METRICS);
    }

    /**
     * 전사 직원 순증감(명). 올해나 전년 값이 없으면 null 이다.
     *
     * <p>명세가 "부문 합과 불일치(산식 확정 필요)"로 열어 둔 값이다. 직원 수 지표의 전년 대비
     * 차이로 정했다. 이미 적재되는 지표라 새 수집 경로가 필요 없고, 부문 증감의 합과 다른
     * 이유도 이 산식이 설명한다 — 인력을 부문별로 공시하지 않은 몫이 전사 숫자에는 들어 있다.
     *
     * <p>비율이 아니라 차이라서 전년이 0 이어도 계산한다. 나눗셈이 없으므로 부호가 뒤집히는
     * 문제도 없다. 증감률과 규칙이 다른 것은 이 값이 증감률이 아니기 때문이다.
     */
    private Integer employeeTotalChange(String corpCode, int year) {
        List<MetricValueProjection> rows =
                metricRepository.findMetricValues(corpCode, TOTAL_METRICS, year, year - 1);
        if (rows.isEmpty()) {
            return null;
        }

        MetricValueProjection employees = rows.getFirst();
        BigDecimal value = employees.getValue();
        BigDecimal prevValue = employees.getPrevValue();
        if (value == null || prevValue == null) {
            return null;
        }
        // metric_value 가 NUMERIC(24,4) 라 인원도 소수 자리를 달고 올라온다. 사람 수에 소수가
        // 있을 리 없지만 정규화가 어긋난 값 하나로 500 이 나가지 않게 반올림해서 받는다.
        return value.subtract(prevValue).setScale(0, RoundingMode.HALF_UP).intValue();
    }

    /**
     * 부문 매출의 단순합. 비중의 분모로만 쓰고 응답에는 나가지 않는다.
     *
     * <p>명세의 이 응답에는 합계 필드가 없다. 기업 개요는 같은 합계를 totalRevenue 로
     * 내보내는데, 두 응답이 같은 값을 서로 다른 자리에 두는 셈이라 계산 규칙은 하나로
     * 맞춰 두었다 — 매출을 공시한 부문만 더한다.
     */
    private BigDecimal totalRevenue(List<SegmentChangeProjection> rows) {
        return rows.stream()
                .map(SegmentChangeProjection::getRevenue)
                .filter(revenue -> revenue != null)
                .reduce(BigDecimal::add)
                .orElse(null);
    }

    private List<CompanySegmentsResponse.Segment> toSegments(List<SegmentChangeProjection> rows,
                                                             BigDecimal totalRevenue) {
        return rows.stream()
                .map(row -> new CompanySegmentsResponse.Segment(
                        row.getSegmentCode(),
                        row.getRevenue(),
                        share(row.getRevenue(), totalRevenue),
                        employeeChange(row)))
                .toList();
    }

    /**
     * 부문 직원 순증감(명). 올해나 전년 인원이 없으면 null 이다.
     *
     * <p>전년 행이 없는 부문(올해 새로 생긴 부문)은 증감을 내지 않는다. 0 에서 늘어난 것으로
     * 보면 신설 부문의 전 인원이 순증가로 잡혀 전사 증감과 크게 어긋난다.
     */
    private Integer employeeChange(SegmentChangeProjection row) {
        Integer current = row.getEmployeeCount();
        Integer previous = row.getPrevEmployeeCount();
        return current == null || previous == null ? null : current - previous;
    }

    /**
     * 부문 매출 비중(%). 부문 매출이 없거나 합계가 0 이하면 null 이다.
     *
     * <p>기업 개요의 비중과 같은 규칙이다. 미공시 부문은 분자가 없어 비중도 null 이고,
     * 그래서 비중의 합이 100 이 안 될 수 있다.
     */
    private BigDecimal share(BigDecimal revenue, BigDecimal totalRevenue) {
        if (revenue == null || totalRevenue == null || totalRevenue.signum() <= 0) {
            return null;
        }
        return revenue.multiply(HUNDRED).divide(totalRevenue, SHARE_SCALE, RoundingMode.HALF_UP);
    }
}

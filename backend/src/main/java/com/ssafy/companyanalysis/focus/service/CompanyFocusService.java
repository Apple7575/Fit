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
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
public class CompanyFocusService {

    private static final BigDecimal HUNDRED = BigDecimal.valueOf(100);

    /** 증가율 소수 자릿수. 지표 조회의 증감률과 같은 1자리다. */
    private static final int RATE_SCALE = 1;

    /** R&D 수치의 원본 지표. 둘 다 카탈로그에 있고 company_metric 에 착지한다. */
    private static final String RD_EXPENSE = "rd_expense";
    private static final String RD_RATIO = "rd_ratio";
    private static final List<String> RND_METRICS = List.of(RD_EXPENSE, RD_RATIO);

    /** 사업 방향 목록의 구분값. 테이블의 CHECK 제약과 같은 문자열이다. */
    private static final String NEW_BUSINESS = "NEW_BUSINESS";
    private static final String KEYWORD = "KEYWORD";

    private final CompanyRepository companyRepository;
    private final CompanyFocusRepository companyFocusRepository;
    private final MetricRepository metricRepository;

    public CompanyFocusService(CompanyRepository companyRepository,
                               CompanyFocusRepository companyFocusRepository,
                               MetricRepository metricRepository) {
        this.companyRepository = companyRepository;
        this.companyFocusRepository = companyFocusRepository;
        this.metricRepository = metricRepository;
    }

    /**
     * 사업 방향과 R&D 지표를 조회한다. 없는 기업은 404 COMPANY_NOT_FOUND 다.
     *
     * <p>두 블록 중 한쪽만 있어도 200 이다. 사업 방향은 AI 분석이 돌아야 생기고 R&D 수치는
     * 지표 적재가 되어야 생기는데, 두 파이프라인의 진행이 같지 않다. 한쪽이 비었다고 응답을
     * 실패로 만들면 이미 있는 쪽도 화면에 못 나간다.
     *
     * @param year 생략하면 이 기업의 집중 분야 데이터가 있는 최신 연도
     */
    @Transactional(readOnly = true)
    public CompanyFocusResponse getFocus(String corpCode, Integer year) {
        requireCompany(corpCode);

        Integer targetYear = resolveYear(corpCode, year);
        if (targetYear == null) {
            // 사업 방향도 R&D 도 한 해도 없다. 조회할 연도가 없을 뿐 오류는 아니므로
            // 두 블록의 골격만 내보낸다. 목록은 null 이 아니라 빈 배열이다.
            return new CompanyFocusResponse(null, emptyDirection(), emptyRnd());
        }

        return new CompanyFocusResponse(targetYear, direction(corpCode, targetYear), rnd(corpCode, targetYear));
    }

    private void requireCompany(String corpCode) {
        if (!companyRepository.existsById(corpCode)) {
            throw new BusinessException(ErrorCode.COMPANY_NOT_FOUND);
        }
    }

    /** 요청 연도가 있으면 그대로, 없으면 집중 분야 데이터의 최신 연도. 둘 다 없으면 null. */
    private Integer resolveYear(String corpCode, Integer year) {
        return year != null ? year : companyFocusRepository.findLatestFiscalYear(corpCode, RND_METRICS);
    }

    /**
     * 사업 방향 블록. 분석이 돌지 않았으면 빈 목록과 null 로 채운다.
     *
     * <p>목록 두 종을 한 번에 읽고 구분값으로 나눈다. 왕복을 둘로 늘리지 않으려는 것이고,
     * 두 목록이 같은 분석 결과에서 나오므로 따로 읽어 시점이 갈릴 이유도 없다.
     */
    private CompanyFocusResponse.Direction direction(String corpCode, int year) {
        List<FocusDirectionItemProjection> items =
                companyFocusRepository.findDirectionItems(corpCode, year);
        String strategyChange = companyFocusRepository.findDirection(corpCode, year)
                .map(FocusDirectionProjection::getStrategyChange)
                .orElse(null);

        return new CompanyFocusResponse.Direction(
                namesOf(items, NEW_BUSINESS), namesOf(items, KEYWORD), strategyChange);
    }

    /** 쿼리가 구분값·순서로 정렬해 오므로 걸러내기만 하면 순서가 유지된다. */
    private List<String> namesOf(List<FocusDirectionItemProjection> items, String itemType) {
        return items.stream()
                .filter(item -> itemType.equals(item.getItemType()))
                .map(FocusDirectionItemProjection::getItemName)
                .toList();
    }

    /**
     * R&D 블록. 금액과 매출 비중은 지표에서 그대로 오고 증가율만 계산한다.
     *
     * <p>비중을 금액 ÷ 매출로 직접 계산하지 않는다. 카탈로그의 rd_ratio 가 이미 그 뜻이고,
     * 같은 숫자를 두 군데서 만들면 규칙이 갈릴 자리가 생긴다.
     */
    private CompanyFocusResponse.Rnd rnd(String corpCode, int year) {
        Map<String, MetricValueProjection> metrics =
                metricRepository.findMetricValues(corpCode, RND_METRICS, year, year - 1).stream()
                        .collect(Collectors.toMap(MetricValueProjection::getMetricCode, Function.identity()));

        MetricValueProjection cost = metrics.get(RD_EXPENSE);
        MetricValueProjection ratio = metrics.get(RD_RATIO);

        return new CompanyFocusResponse.Rnd(
                value(cost),
                cost == null ? null : changeRate(cost.getValue(), cost.getPrevValue()),
                value(ratio),
                companyFocusRepository.findRndFields(corpCode, year));
    }

    /**
     * metric_value 는 NUMERIC(24,4) 라 금액도 {@code 37754815000000.0000} 으로 올라온다.
     * 명세가 기대하는 자릿수는 카탈로그의 value_scale 이다(금액 0, 비율 1).
     */
    private BigDecimal value(MetricValueProjection projection) {
        if (projection == null || projection.getValue() == null) {
            return null;
        }
        return projection.getValue().setScale(projection.getValueScale(), RoundingMode.HALF_UP);
    }

    /**
     * 전년 대비 증가율(%). 전년 값이 없거나 0 이하면 null 이다.
     *
     * <p>전년이 0 이하일 때 계산하지 않는 것은 지표 조회의 증감률과 같은 이유다. 분모가 0 이면
     * 나눌 수 없고, 음수면 부호가 뒤집혀 줄어든 것이 늘어난 것처럼 보인다.
     */
    private BigDecimal changeRate(BigDecimal value, BigDecimal prevValue) {
        if (value == null || prevValue == null || prevValue.signum() <= 0) {
            return null;
        }
        return value.subtract(prevValue)
                .multiply(HUNDRED)
                .divide(prevValue, RATE_SCALE, RoundingMode.HALF_UP);
    }

    private static CompanyFocusResponse.Direction emptyDirection() {
        return new CompanyFocusResponse.Direction(List.of(), List.of(), null);
    }

    private static CompanyFocusResponse.Rnd emptyRnd() {
        return new CompanyFocusResponse.Rnd(null, null, null, List.of());
    }
}

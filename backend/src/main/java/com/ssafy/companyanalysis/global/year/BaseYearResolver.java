package com.ssafy.companyanalysis.global.year;

import com.ssafy.companyanalysis.metric.repository.MetricRepository;
import org.springframework.stereotype.Component;

import java.time.Clock;
import java.time.LocalDate;

/**
 * 여러 기업을 한 해로 묶어 보여주는 화면의 기준연도를 정한다. 비교와 시계열이 쓴다.
 *
 * <p>연도를 상수로 박아두면 적재가 다음 해로 넘어갔을 때 아무도 모른다. 오류가 나지
 * 않고 낡은 해를 계속 보여줄 뿐이라, 누가 상수를 올려주기 전까지 조용히 뒤처진다.
 */
@Component
public class BaseYearResolver {

    /**
     * 직전 사업연도를 기대할 수 있게 되는 달.
     *
     * <p>사업보고서는 사업연도 경과 후 90일 안에 제출해야 한다(자본시장법 159조).
     * 12월 결산이면 3월 말이 기한이라 4월부터다.
     */
    private static final int FILING_SETTLED_MONTH = 4;

    private final MetricRepository metricRepository;
    private final Clock clock;

    public BaseYearResolver(MetricRepository metricRepository, Clock clock) {
        this.metricRepository = metricRepository;
        this.clock = clock;
    }

    /**
     * 기준연도. 달력이 기대하는 해와 실제 적재된 최신 해 중 이른 쪽이다.
     *
     * <p>둘 다 혼자서는 앞서 나간다. 달력만 보면 4월이 되는 순간 직전 사업연도로 넘어가는데,
     * 그때 적재가 아직이면 없는 해를 조회해 값이 전부 null 이 된다. 적재만 보면 3월에 일찍
     * 제출한 한두 기업 때문에 기준이 끌려 올라가고, 그 해에 값이 있는 건 그 기업들뿐이라
     * 비교 화면 대부분이 빈다. 이른 쪽을 고르면 서로가 서로를 붙잡는다.
     *
     * <p>적재가 하나도 없으면 달력을 따른다. 화면이 조회할 해는 있어야 하고, 값이 없는 것과
     * 기준을 못 정하는 것은 다르다.
     */
    public int resolve() {
        int expected = expectedByCalendar();
        Integer loaded = metricRepository.findLatestFiscalYear();
        return loaded == null ? expected : Math.min(expected, loaded);
    }

    private int expectedByCalendar() {
        LocalDate today = LocalDate.now(clock);
        return today.getMonthValue() >= FILING_SETTLED_MONTH
                ? today.getYear() - 1
                : today.getYear() - 2;
    }
}

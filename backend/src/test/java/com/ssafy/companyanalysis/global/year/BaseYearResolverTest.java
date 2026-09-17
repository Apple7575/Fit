package com.ssafy.companyanalysis.global.year;

import com.ssafy.companyanalysis.metric.repository.MetricRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

/**
 * 기준연도가 달력과 적재 상태 어느 한쪽에도 끌려가지 않는지 본다.
 *
 * <p>시계를 고정해서 확인한다. 시스템 시계를 쓰면 3월과 4월의 동작 차이를 볼 수 없고,
 * 해가 바뀔 때마다 테스트가 저절로 깨진다.
 */
class BaseYearResolverTest {

    private static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");

    @Test
    @DisplayName("적재가 앞서 있어도 3월이면 달력이 붙잡아 직전 해를 쓴다")
    void calendarHoldsBackEarlyFilers() {
        // 삼성전자만 2026 을 먼저 제출한 상황. 여기서 2026 으로 넘어가면 나머지가 전부 빈다.
        assertThat(resolve("2027-03-15", 2026)).isEqualTo(2025);
    }

    @Test
    @DisplayName("4월이 지나고 적재도 끝났으면 다음 해로 넘어간다")
    void movesOnWhenBothAgree() {
        assertThat(resolve("2027-05-01", 2026)).isEqualTo(2026);
    }

    @Test
    @DisplayName("4월이 지났어도 적재가 안 됐으면 넘어가지 않는다")
    void loadedDataHoldsBackTheCalendar() {
        // 적재 파이프라인이 아직 안 돌았다. 여기서 2026 을 고르면 화면이 통째로 빈다.
        assertThat(resolve("2027-05-01", 2025)).isEqualTo(2025);
    }

    @Test
    @DisplayName("3월 31일까지는 직전 해, 4월 1일부터 그 다음 해다")
    void switchesOnTheFilingDeadline() {
        assertThat(resolve("2027-03-31", 2026)).isEqualTo(2025);
        assertThat(resolve("2027-04-01", 2026)).isEqualTo(2026);
    }

    @Test
    @DisplayName("적재가 하나도 없으면 달력을 따른다")
    void fallsBackToCalendarWhenNothingLoaded() {
        assertThat(resolve("2027-05-01", null)).isEqualTo(2026);
        assertThat(resolve("2027-02-01", null)).isEqualTo(2025);
    }

    @Test
    @DisplayName("적재가 달력보다 한참 뒤처져 있으면 적재를 따른다")
    void staleDataWins() {
        assertThat(resolve("2027-05-01", 2023)).isEqualTo(2023);
    }

    private int resolve(String today, Integer latestLoadedYear) {
        MetricRepository metricRepository = mock(MetricRepository.class);
        given(metricRepository.findLatestFiscalYear()).willReturn(latestLoadedYear);

        Clock clock = Clock.fixed(
                LocalDate.parse(today).atStartOfDay(SEOUL).toInstant(), SEOUL);

        return new BaseYearResolver(metricRepository, clock).resolve();
    }

    @Test
    @DisplayName("시계는 서울 기준이다 — UTC 로 읽으면 한 해가 밀리는 시각")
    void usesSeoulTime() {
        MetricRepository metricRepository = mock(MetricRepository.class);
        given(metricRepository.findLatestFiscalYear()).willReturn(2026);

        // 서울은 2027-04-01 08:00, UTC 로는 아직 2027-03-31 23:00 이다.
        Clock clock = Clock.fixed(Instant.parse("2027-03-31T23:00:00Z"), SEOUL);

        assertThat(new BaseYearResolver(metricRepository, clock).resolve()).isEqualTo(2026);
    }
}

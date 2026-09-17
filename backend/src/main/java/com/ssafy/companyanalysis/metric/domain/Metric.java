package com.ssafy.companyanalysis.metric.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * 조회 가능한 지표 카탈로그. V2 가 시드하고 이후 마이그레이션이 더한다.
 *
 * <p>행 수를 적어 두지 않는 것은 지표가 늘 때마다 주석이 낡기 때문이다.
 *
 * <p>{@code active} 와 {@code core} 는 다른 것을 뜻한다. {@code active} 는
 * {@code keys} 로 요청할 수 있는가이고, {@code core} 는 {@code keys} 를 주지
 * 않았을 때 기본으로 나가는가다. rd_ratio 처럼 기본에서는 빠졌지만 산업 비교가
 * 직접 요청하는 지표가 있어 둘이 갈렸다(V7). 값 계산에만 쓰는 내부 지표
 * (total_liabilities 등)는 {@code active} 가 false 라 어느 쪽에도 나오지 않는다.
 *
 * <p>{@code metricCode} 는 {@code keys} 쿼리파라미터로 들어오고 응답의
 * {@code metrics[].key} · {@code series[].key} 로 나간다. 값이 그대로
 * 오가므로 컨트롤러에 별도 매핑 코드가 없다.
 */
@Entity
@Table(name = "metric")
public class Metric {

    @Id
    @Column(name = "metric_code", length = 40)
    private String metricCode;

    @Column(name = "name_ko", length = 50, nullable = false)
    private String nameKo;

    @Column(name = "unit", length = 10, nullable = false)
    private String unit;

    /** 응답 직렬화 시 맞출 소수 자릿수. 금액·인원은 0, 근속연수·비율은 1. */
    @Column(name = "value_scale", nullable = false)
    private short valueScale;

    @Column(name = "source_type", length = 20, nullable = false)
    private String sourceType;

    @Column(name = "display_order", nullable = false)
    private short displayOrder;

    @Column(name = "is_active", nullable = false)
    private boolean active;

    @Column(name = "is_core", nullable = false)
    private boolean core;

    protected Metric() {
    }

    public boolean isCore() {
        return core;
    }

    public String getMetricCode() {
        return metricCode;
    }

    public String getNameKo() {
        return nameKo;
    }

    public String getUnit() {
        return unit;
    }

    public short getValueScale() {
        return valueScale;
    }

    public short getDisplayOrder() {
        return displayOrder;
    }
}

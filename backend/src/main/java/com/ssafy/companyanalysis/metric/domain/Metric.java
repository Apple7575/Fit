package com.ssafy.companyanalysis.metric.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * 조회 가능한 지표 카탈로그. V2 시드의 6행이 전부다.
 *
 * <p>{@code metricCode} 가 곧 {@code /metrics/{metric}} 경로변수 값이라
 * 컨트롤러에 별도 매핑 코드가 없다.
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

    protected Metric() {
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

package com.ssafy.companyanalysis.metric.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * 조회 가능한 지표 카탈로그. V2 가 시드하고 이후 마이그레이션이 더한다.
 *
 * <p>행 수를 적어 두지 않는 것은 지표가 늘 때마다 주석이 낡기 때문이다.
 * {@code is_active = false} 인 행도 있으므로(적재 근거만 남기고 API 에는
 * 내보내지 않는 지표) 목록을 뽑을 때는 반드시
 * {@code findByActiveTrue...} 계열을 쓴다.
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

import { useState } from 'react';
import { BarLineChart } from '../../components/charts/BarLineChart';
import { InlineNotice } from '../../components/common/InlineNotice';
import { PillRadioGroup } from '../../components/common/PillRadioGroup';
import {
  KEY_METRIC_KEYS,
  METRIC_LABELS,
  METRIC_UNITS,
  UNIT_LABELS,
  type MetricKey,
} from '../../types/metrics';
import { formatMetricCompact } from '../../utils/formatMetric';
import { TREND_END_YEAR, TREND_START_YEAR } from '../financial-trend/types';
import { useFinancialTrend } from '../financial-trend/useFinancialTrend';

/** 기본 선택 지표. 취준생이 가장 먼저 보는 규모 지표라 매출액. */
export const DEFAULT_TREND_METRIC: MetricKey = 'revenue';

interface GrowthTrendCardProps {
  corpCode: string;
}

const METRIC_OPTIONS = KEY_METRIC_KEYS.map((key) => ({
  value: key,
  label: METRIC_LABELS[key],
}));

/** 5년 추이 카드: 지표 탭 + 막대(값)·꺾은선(증가율) 이중축 차트. 지표 전환은 재조회 없이 클라이언트에서. */
export function GrowthTrendCard({ corpCode }: GrowthTrendCardProps) {
  const [metricKey, setMetricKey] = useState<MetricKey>(DEFAULT_TREND_METRIC);
  const { state, retry } = useFinancialTrend(corpCode);
  const label = METRIC_LABELS[metricKey];
  const unit = METRIC_UNITS[metricKey];
  const unitLabel = UNIT_LABELS[unit];
  const series =
    state.status === 'success'
      ? state.data.find((s) => s.key === metricKey)
      : undefined;

  return (
    <section
      aria-labelledby="growth-trend-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <PillRadioGroup
        label="추이 지표 선택"
        onChange={setMetricKey}
        options={METRIC_OPTIONS}
        value={metricKey}
      />

      <div className="mt-6 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-lg font-extrabold text-slate-950" id="growth-trend-title">
          {label} 추이
        </h3>
        <p className="text-xs font-semibold text-slate-400">
          {TREND_START_YEAR}–{TREND_END_YEAR} 연간 · (단위: {unitLabel}, %)
        </p>
      </div>

      <div className="mt-4">
        {state.status === 'loading' && (
          <div
            aria-busy="true"
            className="flex h-72 animate-pulse items-center justify-center rounded-2xl bg-slate-50"
            role="status"
          >
            <span className="text-sm font-semibold text-slate-400">
              변화 그래프를 불러오는 중입니다
            </span>
          </div>
        )}

        {state.status === 'error' &&
          (state.error.code === 'COMPANY_NOT_FOUND' ? (
            <InlineNotice>
              기업 정보를 찾을 수 없습니다. 기업코드({corpCode})를 확인해 주세요.
            </InlineNotice>
          ) : (
            <InlineNotice onRetry={retry}>
              변화 그래프를 불러오지 못했습니다. {state.error.message}
            </InlineNotice>
          ))}

        {state.status === 'success' &&
          (series ? (
            <BarLineChart
              formatValue={(v) => formatMetricCompact(unit, v)}
              points={series.points.map((p) => ({
                label: String(p.year),
                value: p.value,
                rate: p.changeRate,
              }))}
              rateName="증가율"
              title={`${label} ${TREND_START_YEAR}~${TREND_END_YEAR}년 변화 그래프`}
              valueName={label}
            />
          ) : (
            <p className="py-16 text-center text-sm font-semibold text-slate-400">
              {label} 추이 데이터가 없습니다
            </p>
          ))}
      </div>

      <p className="mt-4 text-xs text-slate-400">
        * 연결 기준 · 사업보고서 기준 · 공시가 없는 연도는 추정하지 않고 비워 둡니다
      </p>
    </section>
  );
}

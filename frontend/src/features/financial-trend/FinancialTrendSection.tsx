import { useState } from 'react';
import { InlineNotice } from '../../components/common/InlineNotice';
import { METRIC_LABELS, type MetricKey } from '../../types/metrics';
import { MetricSelector } from './MetricSelector';
import { TrendChart } from './TrendChart';
import { TREND_END_YEAR, TREND_START_YEAR } from './types';
import { useFinancialTrend } from './useFinancialTrend';

/** 기본 선택 지표. 취준생이 가장 먼저 보는 규모 지표라 매출액. */
export const DEFAULT_TREND_METRIC: MetricKey = 'revenue';

interface FinancialTrendSectionProps {
  corpCode: string;
  /** 초기 선택 지표 (기본 매출액). 이후 선택은 섹션이 자체 관리한다 */
  initialMetricKey?: MetricKey;
}

export function FinancialTrendSection({
  corpCode,
  initialMetricKey = DEFAULT_TREND_METRIC,
}: FinancialTrendSectionProps) {
  const [metricKey, setMetricKey] = useState<MetricKey>(initialMetricKey);
  const { state, retry } = useFinancialTrend(corpCode);
  const label = METRIC_LABELS[metricKey];
  const selected =
    state.status === 'success'
      ? state.data.find((s) => s.key === metricKey)
      : undefined;

  return (
    <section
      aria-labelledby="trend-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2
            className="text-xl font-extrabold text-slate-950 sm:text-2xl"
            id="trend-title"
          >
            최근 5개년 변화
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            {TREND_START_YEAR}~{TREND_END_YEAR}년 {label} 변화 · 연결재무제표
            기준 · 단위: 원
          </p>
        </div>
        <MetricSelector
          label="그래프 지표 선택"
          onChange={setMetricKey}
          value={metricKey}
        />
      </div>

      <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-5">
        {state.status === 'loading' && (
          <div
            aria-busy="true"
            className="flex h-72 animate-pulse items-center justify-center"
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
          (selected ? (
            <TrendChart label={label} series={selected} />
          ) : (
            <p className="py-16 text-center text-sm font-semibold text-slate-400">
              {label} 추이 데이터가 없습니다
            </p>
          ))}
      </div>
    </section>
  );
}

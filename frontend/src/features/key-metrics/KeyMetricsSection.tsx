import { InlineNotice } from '../../components/common/InlineNotice';
import { METRIC_KEYS, METRIC_LABELS } from '../../types/metrics';
import { KeyMetricsGrid } from './KeyMetricsGrid';
import { useKeyMetrics } from './useKeyMetrics';

interface KeyMetricsSectionProps {
  corpCode: string;
  year: number;
}

export function KeyMetricsSection({ corpCode, year }: KeyMetricsSectionProps) {
  const { state, retry } = useKeyMetrics(corpCode, year);

  return (
    <section
      aria-labelledby="key-metrics-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <div className="mb-6">
        <h2
          className="text-xl font-extrabold text-slate-950 sm:text-2xl"
          id="key-metrics-title"
        >
          {year}년 핵심지표
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          {year}년 사업보고서 기준 · 단위는 지표별로 표기
        </p>
      </div>

      {state.status === 'loading' && <LoadingGrid />}

      {state.status === 'error' &&
        (state.error.code === 'COMPANY_NOT_FOUND' ? (
          <InlineNotice>
            기업 정보를 찾을 수 없습니다. 기업코드({corpCode})를 확인해 주세요.
          </InlineNotice>
        ) : (
          <InlineNotice onRetry={retry}>
            핵심지표를 불러오지 못했습니다. {state.error.message}
          </InlineNotice>
        ))}

      {state.status === 'success' && <KeyMetricsGrid metrics={state.data} />}
    </section>
  );
}

function LoadingGrid() {
  return (
    <div
      aria-busy="true"
      className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
      role="status"
    >
      <span className="sr-only">핵심지표를 불러오는 중입니다</span>
      {METRIC_KEYS.map((key) => (
        <div
          className="min-h-32 animate-pulse rounded-2xl border border-slate-200 bg-slate-50 p-5"
          key={key}
        >
          <p className="text-sm font-bold text-slate-600">
            {METRIC_LABELS[key]}
          </p>
          <div className="mt-5 h-6 w-2/3 rounded-full bg-slate-200" />
        </div>
      ))}
    </div>
  );
}

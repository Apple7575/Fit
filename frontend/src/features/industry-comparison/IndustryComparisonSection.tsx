import { useState } from 'react';
import { InlineNotice } from '../../components/common/InlineNotice';
import { METRIC_LABELS, type MetricKey } from '../../types/metrics';
import { formatMetricValue, metricUnitLabel } from '../../utils/formatMetric';
// 지표 pill 라디오 그룹. financial-trend 에서 만든 범용 컴포넌트를 그대로 쓴다.
import { MetricSelector } from '../financial-trend/MetricSelector';
import { barWidthPercent, maxPeerValue } from './barWidth';
import { SortOrderSelector } from './SortOrderSelector';
import { sortPeers } from './sortPeers';
import { useIndustryComparison } from './useIndustryComparison';
import {
  COMPARISON_METRIC_KEYS,
  type IndustryComparison,
  type IndustryPeer,
  type SortOrder,
} from './types';

/** 기본 선택 지표. 규모를 가장 먼저 보게 되므로 매출액. */
export const DEFAULT_COMPARISON_METRIC: MetricKey = 'revenue';

interface IndustryComparisonSectionProps {
  corpCode: string;
}

interface IndustryComparisonViewProps {
  /** 동일 산업 비교 응답 (명세 5번). companies 가 비어 있으면 안내를 보여준다. */
  comparison: IndustryComparison;
  initialMetricKey?: MetricKey;
}

/** 응답의 companies 를 선택한 지표 하나의 행 목록으로 펼친다. */
const toPeers = (
  comparison: IndustryComparison,
  metricKey: MetricKey,
): IndustryPeer[] =>
  comparison.companies.map((company) => ({
    corpCode: company.corpCode,
    corpName: company.corpName,
    isTarget: company.isTarget,
    value: company.values[metricKey] ?? null,
  }));

/** 동일 산업 비교(US-04). corpCode 로 직접 조회하고 로딩·오류 상태를 처리한다. */
export function IndustryComparisonSection({
  corpCode,
}: IndustryComparisonSectionProps) {
  const { state, retry } = useIndustryComparison(corpCode);

  if (state.status !== 'success') {
    return (
      <section
        aria-labelledby="comparison-title"
        className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
      >
        <h2
          className="mb-6 text-xl font-extrabold text-slate-950 sm:text-2xl"
          id="comparison-title"
        >
          같은 산업 비교
        </h2>
        {state.status === 'loading' ? (
          <div
            aria-busy="true"
            className="h-56 animate-pulse rounded-2xl border border-slate-200 bg-slate-50"
            role="status"
          >
            <span className="sr-only">산업 비교를 불러오는 중입니다</span>
          </div>
        ) : state.error.code === 'COMPANY_NOT_FOUND' ? (
          <InlineNotice>
            기업 정보를 찾을 수 없습니다. 기업코드({corpCode})를 확인해 주세요.
          </InlineNotice>
        ) : (
          <InlineNotice onRetry={retry}>
            산업 비교를 불러오지 못했습니다. {state.error.message}
          </InlineNotice>
        )}
      </section>
    );
  }

  return <IndustryComparisonView comparison={state.data} />;
}

export function IndustryComparisonView({
  comparison,
  initialMetricKey = DEFAULT_COMPARISON_METRIC,
}: IndustryComparisonViewProps) {
  const [metricKey, setMetricKey] = useState<MetricKey>(initialMetricKey);
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  const { year, industry, companies } = comparison;
  // 응답이 알려준 지표만 고를 수 있다. 응답에 목록이 없으면 6종 전부.
  const metricOptions =
    comparison.metrics.length > 0 ? comparison.metrics : COMPARISON_METRIC_KEYS;
  const label = METRIC_LABELS[metricKey];
  const unit = metricUnitLabel(metricKey);
  const peers = sortPeers(toPeers(comparison, metricKey), sortOrder);
  const max = maxPeerValue(peers.map((peer) => peer.value));

  return (
    <section
      aria-labelledby="comparison-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <h2
        className="text-xl font-extrabold text-slate-950 sm:text-2xl"
        id="comparison-title"
      >
        같은 산업 비교
      </h2>
      <p className="mt-2 text-sm leading-6 text-slate-500">
        {industry ? (
          <>
            {industry.name} · 동종 {industry.companyCount.toLocaleString('ko-KR')}
            개사 중 {companies.length}개 ·{' '}
          </>
        ) : (
          '산업 정보 없음 · '
        )}
        {year === null ? '' : `${year}년 `}
        {label} 기준
      </p>

      <div className="mt-5 flex flex-col gap-3 border-y border-slate-100 py-4 lg:flex-row lg:items-center lg:justify-between">
        <MetricSelector
          label="비교 지표 선택"
          onChange={setMetricKey}
          options={metricOptions}
          value={metricKey}
        />
        <SortOrderSelector onChange={setSortOrder} value={sortOrder} />
      </div>

      {peers.length === 0 ? (
        <p className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-5 py-10 text-center text-sm font-semibold text-slate-400">
          비교할 동종 기업 정보가 없습니다
        </p>
      ) : (
        <ul className="mt-6 space-y-4">
          {peers.map((peer) => {
            const isLoss = peer.value !== null && peer.value < 0;

            return (
              <li key={peer.corpCode}>
                <div className="flex items-baseline justify-between gap-3">
                  <p className="flex min-w-0 items-baseline gap-2">
                    <span
                      className={`truncate text-sm font-bold ${
                        peer.isTarget ? 'text-blue-700' : 'text-slate-700'
                      }`}
                    >
                      {peer.corpName}
                    </span>
                    {peer.isTarget && (
                      <span className="shrink-0 rounded-full bg-blue-50 px-2 py-0.5 text-xs font-semibold text-blue-700">
                        조회 기업
                      </span>
                    )}
                  </p>
                  {peer.value === null ? (
                    <span className="shrink-0 text-sm font-semibold text-slate-400">
                      미제공
                    </span>
                  ) : (
                    <span className="shrink-0 text-sm">
                      <span
                        className={`font-extrabold ${
                          isLoss ? 'text-rose-600' : 'text-slate-950'
                        }`}
                      >
                        {formatMetricValue(metricKey, peer.value)}
                      </span>
                      <span className="ml-1 font-semibold text-slate-500">
                        {unit}
                      </span>
                    </span>
                  )}
                </div>
                <div
                  aria-hidden="true"
                  className="mt-2 h-2.5 overflow-hidden rounded-full bg-slate-100"
                >
                  <div
                    className={`h-full rounded-full ${
                      isLoss
                        ? 'bg-rose-400'
                        : peer.isTarget
                          ? 'bg-blue-600'
                          : 'bg-slate-300'
                    }`}
                    style={{ width: `${barWidthPercent(peer.value, max)}%` }}
                  />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

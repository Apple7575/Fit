import { useState } from 'react';
import { METRIC_LABELS, type MetricKey } from '../../types/metrics';
import { formatAmount } from '../../utils/formatAmount';
// 지표 6개 pill 라디오 그룹. 특정 기능에 묶이지 않은 범용 컴포넌트지만,
// F-17 작업이 financial-trend 를 대폭 수정 중이라 지금 옮기면 충돌한다.
// 그 작업이 머지된 뒤 components/common 으로 옮기는 것이 맞다.
import { MetricSelector } from '../financial-trend/MetricSelector';
import { barWidthPercent, maxPeerValue } from './barWidth';
import { SortOrderSelector } from './SortOrderSelector';
import { sortPeers } from './sortPeers';
import type { IndustryComparison, SortOrder } from './types';

/** 기본 선택 지표. 규모를 가장 먼저 보게 되므로 매출액. */
export const DEFAULT_COMPARISON_METRIC: MetricKey = 'revenue';

interface IndustryComparisonSectionProps {
  /** 지표별 비교 결과. 선택된 지표에 해당하는 항목이 없으면 안내를 보여준다. */
  comparisons: IndustryComparison[];
  /** 지금 보고 있는 기업. 목록에서 강조 표시한다. */
  corpCode: string;
  initialMetricKey?: MetricKey;
}

export function IndustryComparisonSection({
  comparisons,
  corpCode,
  initialMetricKey = DEFAULT_COMPARISON_METRIC,
}: IndustryComparisonSectionProps) {
  const [metricKey, setMetricKey] = useState<MetricKey>(initialMetricKey);
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  const selected = comparisons.find((item) => item.metricKey === metricKey);
  // 산업명·기준연도는 지표와 무관하게 같으므로, 선택한 지표에 자료가 없어도 그대로 보여준다.
  const context = selected ?? comparisons[0];
  const label = METRIC_LABELS[metricKey];
  const peers = selected ? sortPeers(selected.peers, sortOrder) : [];
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
        {context?.industryName ?? '산업 정보 없음'} · {context?.year ?? '—'}년{' '}
        {label} 기준
      </p>

      <div className="mt-5 flex flex-col gap-3 border-y border-slate-100 py-4 lg:flex-row lg:items-center lg:justify-between">
        <MetricSelector
          label="비교 지표 선택"
          onChange={setMetricKey}
          value={metricKey}
        />
        <SortOrderSelector onChange={setSortOrder} value={sortOrder} />
      </div>

      {peers.length === 0 ? (
        <p className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-5 py-10 text-center text-sm font-semibold text-slate-400">
          {label} 비교 정보가 없습니다
        </p>
      ) : (
        <ul className="mt-6 space-y-4">
          {peers.map((peer) => {
            const isViewedCompany = peer.corpCode === corpCode;
            const isLoss = peer.value !== null && peer.value < 0;

            return (
              <li key={peer.corpCode}>
                <div className="flex items-baseline justify-between gap-3">
                  <p className="flex min-w-0 items-baseline gap-2">
                    <span
                      className={`truncate text-sm font-bold ${
                        isViewedCompany ? 'text-blue-700' : 'text-slate-700'
                      }`}
                    >
                      {peer.corpName}
                    </span>
                    {isViewedCompany && (
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
                        {formatAmount(peer.value)}
                      </span>
                      <span className="ml-1 font-semibold text-slate-500">
                        원
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
                        : isViewedCompany
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

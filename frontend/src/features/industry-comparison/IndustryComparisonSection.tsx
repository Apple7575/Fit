import { METRIC_LABELS } from '../../types/metrics';
import { formatAmount } from '../../utils/formatAmount';
import { barWidthPercent, maxPeerValue } from './barWidth';
import type { IndustryComparison } from './types';

interface IndustryComparisonSectionProps {
  comparison: IndustryComparison;
  /** 지금 보고 있는 기업. 목록에서 강조 표시한다. */
  corpCode: string;
}

export function IndustryComparisonSection({
  comparison,
  corpCode,
}: IndustryComparisonSectionProps) {
  const { metricKey, year, industryName, peers } = comparison;
  const label = METRIC_LABELS[metricKey];
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
        {industryName ?? '산업 정보 없음'} · {year}년 {label} 기준 · 값이 큰
        순서
      </p>

      {peers.length === 0 ? (
        <p className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-5 py-10 text-center text-sm font-semibold text-slate-400">
          비교할 동종 기업 정보가 없습니다
        </p>
      ) : (
        <ul className="mt-6 space-y-4">
          {peers.map((peer) => {
            const isViewedCompany = peer.corpCode === corpCode;

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
                      <span className="font-extrabold text-slate-950">
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
                      isViewedCompany ? 'bg-blue-600' : 'bg-slate-300'
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

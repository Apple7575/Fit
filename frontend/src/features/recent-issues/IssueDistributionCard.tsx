import { DonutChart } from '../../components/charts/DonutChart';
import { InlineNotice } from '../../components/common/InlineNotice';
import type { QueryState } from '../../hooks/useApiQuery';
import { categoryColor } from './categoryStyle';
import type { NewsStats } from './types';

interface IssueDistributionCardProps {
  state: QueryState<NewsStats>;
  onRetry: () => void;
}

/**
 * 이슈 분포 (카테고리별 도넛 + 범례). 404·분포 없음은 숨기고, 그 외 오류는 안내 + 다시 시도.
 */
export function IssueDistributionCard({ state, onRetry }: IssueDistributionCardProps) {
  if (state.status === 'loading') {
    return (
      <div
        aria-busy="true"
        className="h-56 animate-pulse rounded-3xl border border-slate-200 bg-white"
        role="status"
      >
        <span className="sr-only">이슈 분포를 불러오는 중입니다</span>
      </div>
    );
  }
  if (state.status === 'error') {
    if (state.error.status === 404 || state.error.code === 'COMPANY_NOT_FOUND') return null;
    return (
      <InlineNotice onRetry={onRetry}>
        이슈 분포를 불러오지 못했습니다. {state.error.message}
      </InlineNotice>
    );
  }

  const { distribution } = state.data;
  if (distribution.byCategory.length === 0) return null;
  const total =
    distribution.total ?? distribution.byCategory.reduce((acc, c) => acc + c.count, 0);
  const segments = distribution.byCategory.map((c, i) => ({
    label: c.category,
    value: c.count,
    color: categoryColor(c.category, i),
  }));

  return (
    <section
      aria-labelledby="issue-distribution-title"
      className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-base font-extrabold text-slate-950" id="issue-distribution-title">
          이슈 분포
        </h3>
        <span className="text-xs font-semibold text-slate-400">최근 {distribution.days}일</span>
      </div>

      <div className="mt-4 flex flex-col items-center gap-6 sm:flex-row">
        <DonutChart
          center={
            <>
              <span className="text-xs font-medium text-slate-500">총 이슈 수</span>
              <span className="text-lg font-extrabold text-slate-950">
                {total.toLocaleString('ko-KR')}건
              </span>
            </>
          }
          segments={segments}
          title="카테고리별 이슈 분포 도넛 차트"
        />
        <ul aria-label="카테고리별 이슈 분포" className="w-full min-w-0 flex-1 space-y-2">
          {distribution.byCategory.map((c, i) => (
            <li className="flex items-center gap-3 text-sm" key={c.category}>
              <span
                aria-hidden="true"
                className="size-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: categoryColor(c.category, i) }}
              />
              <span className="min-w-0 flex-1 font-semibold text-slate-700">{c.category}</span>
              <span className="w-8 text-right font-bold tabular-nums text-slate-900">
                {c.count.toLocaleString('ko-KR')}
              </span>
              <span className="w-14 text-right text-xs font-semibold tabular-nums text-slate-500">
                {c.ratio === null ? '' : `${c.ratio.toFixed(1)}%`}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

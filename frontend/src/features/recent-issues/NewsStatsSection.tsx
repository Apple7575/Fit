import { InlineNotice } from '../../components/common/InlineNotice';
import type { QueryState } from '../../hooks/useApiQuery';
import type { NewsStats } from './types';

interface NewsStatsSectionProps {
  /** 탭이 한 번 조회한 통계 상태 (카테고리 필터와 공유하므로 여기서 재조회하지 않는다) */
  state: QueryState<NewsStats>;
  onRetry: () => void;
}

/**
 * 뉴스 KPI + 카테고리 분포. AI 분류 통계라 실패해도 목록에는 영향이 없다.
 * 404 는 조용히 숨기고, 그 외 오류는 안내 + 다시 시도.
 */
export function NewsStatsSection({ state, onRetry }: NewsStatsSectionProps) {
  if (state.status === 'loading') {
    return (
      <div
        aria-busy="true"
        className="h-36 animate-pulse rounded-3xl border border-slate-200 bg-slate-50"
        role="status"
      >
        <span className="sr-only">이슈 통계를 불러오는 중입니다</span>
      </div>
    );
  }

  if (state.status === 'error') {
    if (state.error.status === 404 || state.error.code === 'COMPANY_NOT_FOUND') {
      return null;
    }
    return (
      <InlineNotice onRetry={onRetry}>
        이슈 통계를 불러오지 못했습니다. {state.error.message}
      </InlineNotice>
    );
  }

  return <NewsStatsView stats={state.data} />;
}

const count = (n: number | null) =>
  n === null ? '미제공' : `${n.toLocaleString('ko-KR')}건`;

function NewsStatsView({ stats }: { stats: NewsStats }) {
  const { kpis, distribution } = stats;
  const tiles = [
    { label: `최근 ${kpis.recentNewsDays}일 뉴스`, value: count(kpis.recentNewsCount) },
    { label: `중요 이슈 (${kpis.issueDays}일)`, value: count(kpis.importantIssueCount) },
    { label: '투자 이슈', value: count(kpis.investmentIssueCount) },
    { label: '기술 이슈', value: count(kpis.techIssueCount) },
  ];
  const maxCount = Math.max(1, ...distribution.byCategory.map((c) => c.count));

  return (
    <section
      aria-labelledby="news-stats-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <h2 className="sr-only" id="news-stats-title">
        이슈 통계
      </h2>
      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {tiles.map((tile) => (
          <div
            className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3"
            key={tile.label}
          >
            <dt className="text-xs font-bold text-slate-500">{tile.label}</dt>
            <dd
              className={`mt-1 text-xl font-extrabold tabular-nums ${
                tile.value === '미제공' ? 'text-slate-400' : 'text-slate-950'
              }`}
            >
              {tile.value}
            </dd>
          </div>
        ))}
      </dl>

      {distribution.byCategory.length > 0 && (
        <div className="mt-6">
          <h3 className="text-sm font-bold text-slate-700">
            카테고리별 이슈 분포
            <span className="ml-2 text-xs font-medium text-slate-400">
              최근 {distribution.days}일
              {distribution.total !== null &&
                ` · ${distribution.total.toLocaleString('ko-KR')}건`}
            </span>
          </h3>
          <ul className="mt-3 space-y-2" aria-label="카테고리별 이슈 분포">
            {distribution.byCategory.map((c) => (
              <li className="flex items-center gap-3 text-sm" key={c.category}>
                <span className="w-14 shrink-0 font-bold text-slate-700">
                  {c.category}
                </span>
                <span
                  aria-hidden="true"
                  className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100"
                >
                  <span
                    className="block h-full rounded-full bg-blue-500"
                    style={{ width: `${(c.count / maxCount) * 100}%` }}
                  />
                </span>
                <span className="w-24 shrink-0 text-right text-xs font-semibold tabular-nums text-slate-500">
                  {c.count.toLocaleString('ko-KR')}건
                  {c.ratio !== null && ` · ${c.ratio.toFixed(1)}%`}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

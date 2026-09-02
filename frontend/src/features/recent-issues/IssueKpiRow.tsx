import type { QueryState } from '../../hooks/useApiQuery';
import type { NewsStats } from './types';

interface IssueKpiRowProps {
  state: QueryState<NewsStats>;
}

const count = (n: number | null) => (n === null ? '미제공' : n.toLocaleString('ko-KR'));

/**
 * 뉴스 KPI 4장. AI 분류 통계라 실패해도 목록에는 영향이 없다 — 오류·404 는 조용히 숨긴다.
 */
export function IssueKpiRow({ state }: IssueKpiRowProps) {
  if (state.status === 'loading') {
    return (
      <div aria-busy="true" className="grid grid-cols-2 gap-3 lg:grid-cols-4" role="status">
        <span className="sr-only">이슈 통계를 불러오는 중입니다</span>
        {Array.from({ length: 4 }, (_, i) => (
          <div className="h-24 animate-pulse rounded-2xl border border-slate-200 bg-white" key={i} />
        ))}
      </div>
    );
  }
  if (state.status === 'error') return null;

  const { kpis } = state.data;
  const tiles = [
    { label: '최근 뉴스 수', value: count(kpis.recentNewsCount), basis: `${kpis.recentNewsDays}일 기준`, icon: '📰' },
    { label: '중요 이슈 수', value: count(kpis.importantIssueCount), basis: `최근 ${kpis.issueDays}일`, icon: '❗' },
    { label: '투자 이슈', value: count(kpis.investmentIssueCount), basis: `최근 ${kpis.issueDays}일`, icon: '📈' },
    { label: '기술 이슈', value: count(kpis.techIssueCount), basis: `최근 ${kpis.issueDays}일`, icon: '🔬' },
  ];

  return (
    <dl aria-label="뉴스 KPI" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {tiles.map((tile) => (
        <div
          className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm"
          key={tile.label}
        >
          <span
            aria-hidden="true"
            className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-xl"
          >
            {tile.icon}
          </span>
          <div className="min-w-0">
            <dt className="text-xs font-bold text-slate-500">{tile.label}</dt>
            <dd className="mt-0.5 flex items-baseline gap-2">
              <span
                className={`text-2xl font-extrabold tabular-nums ${
                  tile.value === '미제공' ? 'text-slate-400' : 'text-slate-950'
                }`}
              >
                {tile.value}
              </span>
              <span className="text-xs font-medium text-slate-400">{tile.basis}</span>
            </dd>
          </div>
        </div>
      ))}
    </dl>
  );
}

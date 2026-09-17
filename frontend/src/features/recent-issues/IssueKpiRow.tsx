import { CharacterSlot } from '../../components/brand/CharacterSlot';
import type { QueryState } from '../../hooks/useApiQuery';
import type { NewsStats } from './types';

interface IssueKpiRowProps {
  state: QueryState<NewsStats>;
}

/**
 * 뉴스 KPI. 값이 있는 것만 카드로 보여주고, AI 분류가 아직 없어 비는 항목은 "미제공" 카드로
 * 줄을 채우지 않고 한 줄로 접는다 (0 으로 위장하지 않는다). 통계 API 실패·404 는 조용히 숨긴다.
 */
export function IssueKpiRow({ state }: IssueKpiRowProps) {
  if (state.status === 'loading') {
    return (
      <div aria-busy="true" className="grid grid-cols-2 gap-3 lg:grid-cols-4" role="status">
        <span className="sr-only">이슈 통계를 불러오는 중입니다</span>
        {Array.from({ length: 4 }, (_, i) => (
          <div
            className="h-24 animate-pulse rounded-2xl border border-slate-200 bg-white"
            key={i}
          />
        ))}
      </div>
    );
  }
  if (state.status === 'error') return null;

  const { kpis } = state.data;
  const tiles = [
    {
      label: '최근 뉴스 수',
      value: kpis.recentNewsCount,
      basis: `${kpis.recentNewsDays}일 기준`,
      icon: '📰',
    },
    {
      label: '중요 이슈 수',
      value: kpis.importantIssueCount,
      basis: `최근 ${kpis.issueDays}일`,
      icon: '❗',
    },
    {
      label: '투자 이슈',
      value: kpis.investmentIssueCount,
      basis: `최근 ${kpis.issueDays}일`,
      icon: '📈',
    },
    {
      label: '기술 이슈',
      value: kpis.techIssueCount,
      basis: `최근 ${kpis.issueDays}일`,
      icon: '🔬',
    },
  ];
  const available = tiles.filter((t) => t.value !== null);
  const missing = tiles.filter((t) => t.value === null);

  if (available.length === 0) {
    return (
      <div className="flex items-center gap-4 rounded-2xl border border-dashed border-slate-300 bg-white px-5 py-4">
        <CharacterSlot character="fox" hideLabel size={48} />
        <p className="text-sm font-semibold text-slate-500">
          이 기업은 아직 뉴스 수집 대상이 아니에요. 뉴스가 쌓이면 여기에 통계가 나옵니다.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <dl aria-label="뉴스 KPI" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {available.map((tile) => (
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
                <span className="text-2xl font-extrabold tabular-nums text-slate-950">
                  {(tile.value as number).toLocaleString('ko-KR')}
                </span>
                <span className="text-xs font-medium text-slate-400">{tile.basis}</span>
              </dd>
            </div>
          </div>
        ))}
      </dl>
      {missing.length > 0 && (
        <p className="text-xs text-slate-400">
          {missing.map((t) => t.label).join(' · ')} 은(는) AI 분류가 아직 없어 표시하지 않습니다.
        </p>
      )}
    </div>
  );
}

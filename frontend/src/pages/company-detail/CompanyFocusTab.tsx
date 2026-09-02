import { useOutletContext } from 'react-router-dom';
import { DirectionCard } from '../../features/focus-areas/DirectionCard';
import { EvidenceCard } from '../../features/focus-areas/EvidenceCard';
import { FocusSummaryCard } from '../../features/focus-areas/FocusSummaryCard';
import {
  useAllActivities,
  useEmployeeTrend,
  useFocus,
  useWorkforce,
} from '../../features/focus-areas/hooks';
import { InvestmentTimelineCard } from '../../features/focus-areas/InvestmentTimelineCard';
import { RndCard } from '../../features/focus-areas/RndCard';
import { WorkforceCard } from '../../features/focus-areas/WorkforceCard';
import type { CompanyDetailOutletContext } from './CompanyDetailPage';

/**
 * 집중 분야 탭.
 * 요약(조건부) → [사업 방향(조건부) | R&D(조건부) | 투자(확정)] → [인력 변화(확정) | 판단 근거]
 * 네 API(focus·activities·segments·employee timeseries)는 서로 독립이라 하나가 실패해도
 * 나머지는 그대로 보인다. 조건부 카드는 데이터가 없으면 자리를 차지하지 않는다.
 */
export function CompanyFocusTab() {
  const { corpCode } = useOutletContext<CompanyDetailOutletContext>();
  const focus = useFocus(corpCode);
  const activities = useAllActivities(corpCode);
  const workforce = useWorkforce(corpCode);
  const trend = useEmployeeTrend(corpCode);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-extrabold tracking-tight text-slate-950 sm:text-3xl">
          기업 집중 분야 분석
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          최근 투자·R&amp;D·인력 증가를 기준으로 도출된 집중 분야
        </p>
      </div>

      <FocusSummaryCard state={focus.state} />

      <div className="grid gap-4 lg:grid-cols-3">
        <DirectionCard state={focus.state} />
        <RndCard state={focus.state} />
        <InvestmentTimelineCard onRetry={activities.retry} state={activities.state} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,1fr)]">
        <WorkforceCard
          onRetryTrend={trend.retry}
          onRetryWorkforce={workforce.retry}
          trend={trend.state}
          workforce={workforce.state}
        />
        <EvidenceCard activities={activities.state} focus={focus.state} workforce={workforce.state} />
      </div>
    </div>
  );
}

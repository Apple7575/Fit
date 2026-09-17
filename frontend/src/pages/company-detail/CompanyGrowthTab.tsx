import { useOutletContext } from 'react-router-dom';
import { InlineNotice } from '../../components/common/InlineNotice';
import { useFinancialTrend } from '../../features/financial-trend/useFinancialTrend';
import { GrowthKpiRow } from '../../features/growth-analysis/GrowthKpiRow';
import { GrowthTrendCard } from '../../features/growth-analysis/GrowthTrendCard';
import { ProfitabilityCard } from '../../features/growth-analysis/ProfitabilityCard';
import { YoyCard } from '../../features/growth-analysis/YoyCard';
import { useKeyMetrics } from '../../features/key-metrics/useKeyMetrics';
import type { CompanyDetailOutletContext } from './CompanyDetailPage';
import { DetailHeader } from './DetailHeader';

/**
 * 성장 탭: 머리 → 기준연도 KPI 6장 → [5년 추이 차트 | 전년 대비 · 수익성/안정성].
 * 기준연도는 기본정보의 dataYear 를 따르고, 5년 추이의 구간(to)도 같은 해로 맞춘다.
 * 연도는 화면에서 정하지 않는다 — 머리·차트의 구간은 시계열 응답의 range 그대로다.
 * 기본정보가 확정되기 전에는 지표를 조회하지 않아
 * (연도 없이 한 번, 연도 붙여 한 번 부르는 이중 호출 방지) 자리만 잡아둔다.
 */
export function CompanyGrowthTab() {
  const { corpCode, detailState } = useOutletContext<CompanyDetailOutletContext>();
  const detail = detailState.status === 'success' ? detailState.data : null;

  if (detailState.status === 'loading') {
    return (
      <section
        aria-busy="true"
        className="h-72 animate-pulse rounded-3xl border border-slate-200 bg-white shadow-sm"
        role="status"
      >
        <span className="sr-only">기준연도를 확인하는 중입니다</span>
      </section>
    );
  }

  return <GrowthBody corpCode={corpCode} year={detail?.dataYear ?? null} />;
}

function GrowthBody({ corpCode, year }: { corpCode: string; year: number | null }) {
  const { state, retry } = useKeyMetrics(corpCode, year);
  const trend = useFinancialTrend(corpCode, year);
  const range =
    trend.state.status === 'success'
      ? { from: trend.state.data.from, to: trend.state.data.to }
      : null;

  return (
    <div className="space-y-5">
      <DetailHeader
        description={`최근 5년 성장 분석${range ? ` (${range.from}–${range.to})` : ''}`}
        tab="growth"
      />

      {state.status === 'loading' && (
        <div
          aria-busy="true"
          className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6"
          role="status"
        >
          <span className="sr-only">핵심지표를 불러오는 중입니다</span>
          {Array.from({ length: 6 }, (_, i) => (
            <div className="h-28 animate-pulse rounded-2xl border border-slate-200 bg-white" key={i} />
          ))}
        </div>
      )}

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

      {state.status === 'success' && <GrowthKpiRow data={state.data} />}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(320px,1fr)]">
        <GrowthTrendCard corpCode={corpCode} onRetry={trend.retry} state={trend.state} />
        {state.status === 'success' && (
          <div className="space-y-4">
            <YoyCard metrics={state.data.metrics} year={state.data.year ?? year} />
            {state.data.profitability && (
              <ProfitabilityCard
                profitability={state.data.profitability}
                year={state.data.year ?? year}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

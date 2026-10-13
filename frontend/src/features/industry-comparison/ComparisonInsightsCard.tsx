import type { ComparisonInsightsState } from './useComparisonInsights';

interface ComparisonInsightsCardProps {
  state: ComparisonInsightsState;
}

/**
 * 핵심 인사이트 (규칙 기반 생성). 로딩은 자리만, 404·빈 응답·오류는 조용히 숨긴다 —
 * 비교 화면의 보조 정보라 실패해도 차트·표에 영향이 없어야 한다.
 */
export function ComparisonInsightsCard({ state }: ComparisonInsightsCardProps) {
  if (state.status === 'loading') {
    return (
      <div
        aria-busy="true"
        className="h-full min-h-40 animate-pulse rounded-3xl border border-slate-200 bg-slate-50"
        role="status"
      >
        <span className="sr-only">핵심 인사이트를 생성하는 중입니다</span>
      </div>
    );
  }
  // 없으면 통째로 숨긴다. "준비 중" 카드를 띄우면 차트 옆에 빈 칸만 한 덩이 남는다
  if (state.status === 'error' || state.data.length === 0) return null;

  return (
    <section
      aria-labelledby="comparison-insights-title"
      className="rounded-[var(--radius-card)] bg-white p-5 shadow-[var(--shadow-card)] ring-1 ring-slate-200/70"
    >
      <h3
        className="flex items-center gap-2 text-base font-extrabold text-slate-950"
        id="comparison-insights-title"
      >
        <span aria-hidden="true" className="text-blue-600">✦</span>
        핵심 인사이트
      </h3>
      <ul className="mt-4 space-y-3">
        {state.data.map((insight) => (
          <li
            className="rounded-2xl bg-slate-50 px-4 py-3"
            key={insight.title}
          >
            <p className="text-sm font-bold text-blue-700">{insight.title}</p>
            {insight.body && (
              <p className="mt-1 text-sm leading-6 text-slate-600">{insight.body}</p>
            )}
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[11px] text-slate-400">
        * 선택한 비교 기업들의 수치를 바탕으로 작성한 문장입니다
      </p>
    </section>
  );
}

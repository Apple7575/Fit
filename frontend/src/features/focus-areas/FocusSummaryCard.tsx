import { SourceBadge } from '../../components/common/SourceBadge';
import type { FocusState } from './hooks';

interface FocusSummaryCardProps {
  state: FocusState;
}

/** 요약 칩: 키워드 → 신규 사업 순으로 중복 없이 최대 3개 */
export function pickSummaryChips(
  keywords: string[],
  newBusiness: string[],
  limit = 3,
): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const item of [...keywords, ...newBusiness]) {
    if (!seen.has(item)) {
      seen.add(item);
      out.push(item);
      if (out.length === limit) break;
    }
  }
  return out;
}

/**
 * 집중 분야 요약 (조건부): 사업 방향의 키워드·전략 변화를 한 줄로. AI 생성물이라 배지로 구분한다.
 * direction 이 없으면(404·빈 데이터) 통째로 숨긴다.
 */
export function FocusSummaryCard({ state }: FocusSummaryCardProps) {
  if (state.status === 'loading') {
    return (
      <div
        aria-busy="true"
        className="h-32 animate-pulse rounded-3xl border border-slate-200 bg-white"
        role="status"
      >
        <span className="sr-only">집중 분야 요약을 불러오는 중입니다</span>
      </div>
    );
  }
  if (state.status === 'error' || !state.data.direction) return null;

  const { direction } = state.data;
  const chips = pickSummaryChips(direction.keywords, direction.newBusiness);
  if (chips.length === 0 && !direction.strategyChange) return null;

  return (
    <section
      aria-labelledby="focus-summary-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm"
    >
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center">
        <div className="shrink-0 lg:w-36">
          <h3 className="text-base font-extrabold text-slate-950" id="focus-summary-title">
            집중 분야 요약
          </h3>
          <div className="mt-2">
            <SourceBadge kind="ai" />
          </div>
        </div>
        {chips.length > 0 && (
          <ul aria-label="집중 분야 키워드" className="flex flex-wrap gap-3">
            {chips.map((chip) => (
              <li
                className="rounded-2xl border border-violet-100 bg-violet-50 px-5 py-3 text-base font-extrabold text-violet-800"
                key={chip}
              >
                {chip}
              </li>
            ))}
          </ul>
        )}
        {direction.strategyChange && (
          <p className="text-sm leading-6 text-slate-600 lg:flex-1">
            {direction.strategyChange}
          </p>
        )}
      </div>
    </section>
  );
}

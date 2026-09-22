import { EmptyCard } from '../../components/common/EmptyCard';
import { SourceBadge } from '../../components/common/SourceBadge';
import type { FocusState } from './hooks';

interface DirectionCardProps {
  state: FocusState;
}

/** 사업 방향 (조건부): 신규 사업 · 핵심 사업 키워드 · 전략 변화. AI 생성물. 없으면 숨김. */
export function DirectionCard({ state }: DirectionCardProps) {
  if (state.status === 'loading') {
    return (
      <div
        aria-busy="true"
        className="h-64 animate-pulse rounded-[var(--radius-card)] bg-white shadow-[var(--shadow-card)] ring-1 ring-slate-200/70"
        role="status"
      >
        <span className="sr-only">사업 방향을 불러오는 중입니다</span>
      </div>
    );
  }
  if (state.status === 'error' || !state.data.direction) {
    return (
      <EmptyCard title="사업 방향">
        공시에서 뽑은 사업 방향 정보가 아직 없어요. 사업 탭의 사업부 구성과 주요 제품을 참고하세요.
      </EmptyCard>
    );
  }
  const { newBusiness, keywords, strategyChange } = state.data.direction;

  const rows: Array<{ label: string; value: string }> = [
    { label: '신규 사업', value: newBusiness.join(', ') },
    { label: '핵심 사업 키워드', value: keywords.join(', ') },
    { label: '전략 변화', value: strategyChange ?? '' },
  ].filter((row) => row.value !== '');

  return (
    <section
      aria-labelledby="direction-title"
      className="rounded-[var(--radius-card)] bg-white p-5 shadow-[var(--shadow-card)] ring-1 ring-slate-200/70"
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-base font-extrabold text-slate-950" id="direction-title">
          사업 방향
        </h3>
        <SourceBadge kind="ai" source="사업보고서 문장 분석" />
      </div>
      <ul className="mt-4 space-y-3">
        {rows.map((row) => (
          <li className="rounded-2xl bg-slate-50 px-4 py-3" key={row.label}>
            <p className="text-sm font-bold text-blue-700">{row.label}</p>
            <p className="mt-1 text-sm leading-6 text-slate-700">{row.value}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

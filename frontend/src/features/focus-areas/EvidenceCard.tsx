import { EmptyCard } from '../../components/common/EmptyCard';
import { SourceBadge } from '../../components/common/SourceBadge';
import { buildEvidenceRows } from './evidence';
import type { ActivitiesState, FocusState, WorkforceState } from './hooks';

interface EvidenceCardProps {
  focus: FocusState;
  activities: ActivitiesState;
  workforce: WorkforceState;
}

/** 판단 근거 (데이터 기반 요약). 세 API 중 도착한 것만으로 만들며, 근거가 없으면 숨긴다. */
export function EvidenceCard({ focus, activities, workforce }: EvidenceCardProps) {
  const loading =
    focus.status === 'loading' || activities.status === 'loading' || workforce.status === 'loading';
  if (loading) {
    return (
      <div
        aria-busy="true"
        className="h-64 animate-pulse rounded-[var(--radius-card)] bg-white shadow-[var(--shadow-card)] ring-1 ring-slate-200/70"
        role="status"
      >
        <span className="sr-only">판단 근거를 정리하는 중입니다</span>
      </div>
    );
  }

  const rows = buildEvidenceRows(
    focus.status === 'success' ? focus.data : null,
    activities.status === 'success' ? activities.data : null,
    workforce.status === 'success' ? workforce.data : null,
  );
  if (rows.length === 0) {
    return (
      <EmptyCard title="근거">
        이 기업은 공시에서 뽑은 근거가 아직 쌓이지 않았어요.
      </EmptyCard>
    );
  }

  return (
    <section
      aria-labelledby="evidence-title"
      className="rounded-[var(--radius-card)] bg-white p-5 shadow-[var(--shadow-card)] ring-1 ring-slate-200/70"
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-base font-extrabold text-slate-950" id="evidence-title">
          판단 근거
        </h3>
        <SourceBadge kind="data" source="공시 수치 기반" />
      </div>
      <ul className="mt-4 space-y-3">
        {rows.map((row) => (
          <li
            className="flex items-start gap-3 rounded-2xl border border-slate-200 px-4 py-3"
            key={row.label}
          >
            <span aria-hidden="true" className="mt-0.5 text-blue-600">✓</span>
            <div className="min-w-0">
              <p className="text-sm font-bold text-slate-900">{row.label}</p>
              <p className="mt-0.5 text-sm leading-6 text-slate-600">{row.body}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

import { SourceBadge } from '../../components/common/SourceBadge';
import { formatMetricCompact } from '../../utils/formatMetric';
import type { FocusState } from './hooks';

interface RndCardProps {
  state: FocusState;
}

const signed = (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(1)}%`;

/** R&D (조건부): 비용 · 전년 대비 증가율 · 매출 대비 비율 · 주요 연구 분야. 공시 수치. 없으면 숨김. */
export function RndCard({ state }: RndCardProps) {
  if (state.status === 'loading') {
    return (
      <div
        aria-busy="true"
        className="h-64 animate-pulse rounded-3xl border border-slate-200 bg-white"
        role="status"
      >
        <span className="sr-only">R&amp;D 정보를 불러오는 중입니다</span>
      </div>
    );
  }
  if (state.status === 'error' || !state.data.rnd) return null;
  const { rnd } = state.data;

  const rows: Array<{ label: string; value: string | null; tone?: string }> = [
    { label: 'R&D 비용', value: rnd.expense === null ? null : `${formatMetricCompact('KRW', rnd.expense)} 원` },
    {
      label: '전년 대비 증가율',
      value: rnd.growthRate === null ? null : signed(rnd.growthRate),
      tone: rnd.growthRate === null ? undefined : rnd.growthRate >= 0 ? 'text-blue-700' : 'text-rose-700',
    },
    { label: '매출 대비 R&D 비율', value: rnd.revenueRatio === null ? null : `${rnd.revenueRatio.toFixed(1)}%` },
  ];

  return (
    <section
      aria-labelledby="rnd-title"
      className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-base font-extrabold text-slate-950" id="rnd-title">
          R&amp;D
        </h3>
        <SourceBadge kind="data" source="DART 사업보고서" />
      </div>
      <dl className="mt-4 divide-y divide-slate-100 rounded-2xl border border-slate-200">
        {rows.map((row) => (
          <div className="flex items-center justify-between gap-3 px-4 py-3" key={row.label}>
            <dt className="text-sm font-semibold text-slate-600">{row.label}</dt>
            <dd
              className={`text-sm font-extrabold tabular-nums ${
                row.value === null ? 'text-slate-400' : (row.tone ?? 'text-slate-950')
              }`}
            >
              {row.value ?? '미제공'}
            </dd>
          </div>
        ))}
      </dl>
      {rnd.fields.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-bold text-slate-500">주요 연구 분야</p>
          <ul aria-label="주요 연구 분야" className="mt-2 flex flex-wrap gap-2">
            {rnd.fields.map((field) => (
              <li
                className="rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-700"
                key={field}
              >
                {field}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

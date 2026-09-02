import { SourceBadge } from '../../components/common/SourceBadge';
import { formatHeadcountChange } from '../../utils/formatHeadcount';
import { formatMetricCompact } from '../../utils/formatMetric';
import type { ActivitiesState, FocusState, WorkforceState } from './hooks';
import type { CompanyFocus, InvestmentActivity, WorkforceChange } from './types';

interface EvidenceCardProps {
  focus: FocusState;
  activities: ActivitiesState;
  workforce: WorkforceState;
}

export interface EvidenceRow {
  label: string;
  body: string;
}

const signed = (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(1)}%`;

/**
 * 판단 근거 문장을 데이터에서 규칙으로 만든다. 값이 있는 항목만, 판정 없이 사실만 적는다.
 * (데이터가 없는 항목은 만들지 않는다 — "0" 이나 추정 문장 금지)
 */
export function buildEvidenceRows(
  focus: CompanyFocus | null,
  activities: InvestmentActivity[] | null,
  workforce: WorkforceChange | null,
): EvidenceRow[] {
  const rows: EvidenceRow[] = [];

  const disclosed = (workforce?.segments ?? []).filter((s) => s.revenueShare !== null);
  if (disclosed.length > 0) {
    rows.push({
      label: '사업부 매출 비중',
      body: disclosed
        .map((s) => `${s.name} 부문(${(s.revenueShare as number).toFixed(1)}%)`)
        .join(', '),
    });
  }

  const rnd = focus?.rnd;
  if (rnd && (rnd.expense !== null || rnd.growthRate !== null)) {
    const parts: string[] = [];
    if (rnd.expense !== null) parts.push(`R&D 비용 ${formatMetricCompact('KRW', rnd.expense)} 원`);
    if (rnd.growthRate !== null) parts.push(`전년 대비 ${signed(rnd.growthRate)}`);
    rows.push({
      label: rnd.growthRate !== null && rnd.growthRate < 0 ? 'R&D 감소' : 'R&D 투자',
      body: parts.join('으로 '),
    });
  }

  const recent = (activities ?? []).filter((a) => a.purpose !== null).slice(0, 2);
  if (recent.length > 0) {
    rows.push({
      label: '신규 투자',
      body: `${recent.map((a) => `${a.purpose}(${a.year})`).join(', ')} 등 공시된 투자 진행`,
    });
  }

  const total = workforce?.employeeTotalChange ?? null;
  if (total !== null) {
    const grown = (workforce?.segments ?? [])
      .filter((s) => s.employeeChange !== null && s.employeeChange > 0)
      .sort((a, b) => (b.employeeChange as number) - (a.employeeChange as number))
      .slice(0, 2)
      .map((s) => s.name);
    rows.push({
      label: total < 0 ? '인력 감소' : '인력 증가',
      body:
        `전사 인원 ${formatHeadcountChange(total)}` +
        (grown.length > 0 ? `, ${grown.join('·')} 중심 인력 변화` : ''),
    });
  }

  return rows;
}

/** 판단 근거 (데이터 기반 요약). 세 API 중 도착한 것만으로 만들며, 근거가 없으면 숨긴다. */
export function EvidenceCard({ focus, activities, workforce }: EvidenceCardProps) {
  const loading =
    focus.status === 'loading' || activities.status === 'loading' || workforce.status === 'loading';
  if (loading) {
    return (
      <div
        aria-busy="true"
        className="h-64 animate-pulse rounded-3xl border border-slate-200 bg-white"
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
  if (rows.length === 0) return null;

  return (
    <section
      aria-labelledby="evidence-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm"
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

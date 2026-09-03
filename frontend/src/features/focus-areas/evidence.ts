import { formatHeadcountChange } from '../../utils/formatHeadcount';
import { formatMetricCompact } from '../../utils/formatMetric';
import type { CompanyFocus, InvestmentActivity, WorkforceChange } from './types';

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

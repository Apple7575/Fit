/** 카테고리별 칩 색. 모르는 카테고리는 회색. 색만이 아니라 글자로도 구분된다. */
const CHIP: Record<string, string> = {
  투자: 'bg-blue-50 text-blue-700',
  기술: 'bg-emerald-50 text-emerald-700',
  실적: 'bg-violet-50 text-violet-700',
  인사: 'bg-amber-50 text-amber-700',
  리스크: 'bg-rose-50 text-rose-700',
  제품: 'bg-sky-50 text-sky-700',
  규제: 'bg-orange-50 text-orange-700',
};

const DOT: Record<string, string> = {
  투자: '#2563eb',
  기술: '#10b981',
  실적: '#8b5cf6',
  인사: '#f59e0b',
  리스크: '#f43f5e',
  제품: '#0ea5e9',
  규제: '#f97316',
};

const FALLBACK_DOTS = ['#64748b', '#94a3b8', '#cbd5e1', '#475569', '#334155'];

export const categoryChipClass = (category: string): string =>
  CHIP[category] ?? 'bg-slate-100 text-slate-600';

/** 도넛·범례용 색. 정해진 색이 없는 카테고리는 순서대로 회색 계열을 배정한다. */
export const categoryColor = (category: string, index: number): string =>
  DOT[category] ?? FALLBACK_DOTS[index % FALLBACK_DOTS.length];

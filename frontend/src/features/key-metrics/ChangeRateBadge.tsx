import { formatChangeRate } from '../../utils/formatChangeRate';

interface ChangeRateBadgeProps {
  /** 전년 대비 증감률(%) */
  changeRate: number;
  /** 앞에 붙는 설명(스크린리더용). 기본 "전년 대비" */
  prefix?: string;
}

/**
 * 증감률 배지. 상승·하락을 색만이 아니라 화살표 문자로도 구분한다.
 */
export function ChangeRateBadge({
  changeRate,
  prefix = '전년 대비',
}: ChangeRateBadgeProps) {
  const tone =
    changeRate > 0
      ? 'bg-emerald-50 text-emerald-700'
      : changeRate < 0
        ? 'bg-rose-50 text-rose-700'
        : 'bg-slate-100 text-slate-600';
  const arrow = changeRate > 0 ? '▲' : changeRate < 0 ? '▼' : '─';

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-bold ${tone}`}
    >
      <span aria-hidden="true">{arrow}</span>
      <span className="sr-only">{prefix} </span>
      {formatChangeRate(changeRate)}
    </span>
  );
}

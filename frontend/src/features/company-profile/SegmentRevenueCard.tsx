import { formatAmount } from '../../utils/formatAmount';
import type { ProfileSegment } from './types';

interface SegmentRevenueCardProps {
  segments: ProfileSegment[];
  totalRevenue: number | null;
}

const COLORS = ['#2563eb', '#8b5cf6', '#38bdf8', '#f59e0b', '#10b981', '#f43f5e'];
/** 둘레가 정확히 100 이 되는 반지름 → stroke-dasharray 를 % 처럼 쓴다 */
const RADIUS = 15.915494309189535;

/** 사업부 매출 도넛. 매출 미공시 부문은 호에서 제외하고 범례에 "미공시" 로 남긴다. */
export function SegmentRevenueCard({
  segments,
  totalRevenue,
}: SegmentRevenueCardProps) {
  const disclosed = segments.filter((s) => s.revenue !== null);
  if (disclosed.length === 0) {
    return null;
  }

  const sum = disclosed.reduce((acc, s) => acc + (s.revenue ?? 0), 0);
  let cursor = 25; // 12시 방향에서 시작
  const arcs = disclosed.map((segment, index) => {
    const ratio = sum > 0 ? ((segment.revenue ?? 0) / sum) * 100 : 0;
    const arc = {
      segment,
      ratio,
      offset: cursor,
      color: COLORS[index % COLORS.length],
    };
    cursor -= ratio;
    return arc;
  });
  const undisclosed = segments.filter((s) => s.revenue === null);

  return (
    <section
      aria-labelledby="segment-revenue-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <h2
        className="text-xl font-extrabold text-slate-950"
        id="segment-revenue-title"
      >
        사업부 매출
      </h2>

      <div className="mt-6 flex flex-col items-center gap-8 sm:flex-row">
        <div className="relative size-44 shrink-0">
          <svg aria-hidden="true" className="size-full" viewBox="0 0 42 42">
            {arcs.map(({ segment, ratio, offset, color }) => (
              <circle
                cx="21"
                cy="21"
                data-testid="donut-arc"
                fill="none"
                key={segment.code}
                r={RADIUS}
                stroke={color}
                strokeDasharray={`${ratio} ${100 - ratio}`}
                strokeDashoffset={offset}
                strokeWidth="6"
              />
            ))}
          </svg>
          {totalRevenue !== null && (
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-xs font-medium text-slate-500">
                전체 매출
              </span>
              <span className="text-sm font-extrabold text-slate-950">
                {formatAmount(totalRevenue)} 원
              </span>
            </div>
          )}
        </div>

        <ul className="w-full min-w-0 flex-1 space-y-2.5">
          {arcs.map(({ segment, ratio, color }) => (
            <li
              className="flex items-center gap-3 rounded-xl bg-slate-50 px-4 py-2.5 text-sm"
              key={segment.code}
            >
              <span
                aria-hidden="true"
                className="size-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: color }}
              />
              <span className="min-w-0 flex-1 truncate font-bold text-slate-900">
                {segment.code}
              </span>
              <span className="font-medium text-slate-600">
                {formatAmount(segment.revenue ?? 0)} 원
              </span>
              <span className="w-14 text-right font-semibold text-slate-500">
                {(segment.revenueShare ?? ratio).toFixed(1)}%
              </span>
            </li>
          ))}
          {undisclosed.map((segment) => (
            <li
              className="flex items-center gap-3 rounded-xl bg-slate-50 px-4 py-2.5 text-sm"
              key={segment.code}
            >
              <span
                aria-hidden="true"
                className="size-2.5 shrink-0 rounded-full bg-slate-300"
              />
              <span className="min-w-0 flex-1 truncate font-bold text-slate-900">
                {segment.code}
              </span>
              <span className="font-medium text-slate-400">미공시</span>
            </li>
          ))}
        </ul>
      </div>

      <p className="mt-5 text-xs text-slate-400">* 연결 기준 매출액</p>
    </section>
  );
}

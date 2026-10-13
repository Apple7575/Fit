import { EmptyCard } from '../../components/common/EmptyCard';
import { useState } from 'react';
import { formatAmount } from '../../utils/formatAmount';
import { realUndisclosed } from './segmentName';
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
  const [hover, setHover] = useState<string | null>(null);
  const disclosed = segments.filter((s) => s.revenue !== null);
  if (disclosed.length === 0) {
    return (
      <EmptyCard title="사업부 매출">
        사업부별 매출을 공시하지 않는 기업이에요. 전체 매출은 성장 탭에서 볼 수 있습니다.
      </EmptyCard>
    );
  }

  const sum = disclosed.reduce((acc, s) => acc + (s.revenue ?? 0), 0);
  // 색은 공시된 순서대로 정해 둔다. 그래프에서 빠지는 항목도 범례에서는 같은 색을 쓴다
  const colorOf = new Map(disclosed.map((s, i) => [s.code, COLORS[i % COLORS.length]]));

  /*
   * 매출이 0 이하인 항목은 호로 그릴 수 없다 (연결 조정처럼 빼는 몫이 음수로 공시된다).
   * 길이가 음수인 stroke-dasharray 는 값 전체가 무효가 되어 그 조각이 원 하나를 꽉 채워
   * 버리고, 마지막에 그려지므로 앞의 조각들을 전부 덮는다. 그래서 호에서는 뺀다.
   */
  const positives = disclosed.filter((s) => (s.revenue ?? 0) > 0);
  const arcTotal = positives.reduce((acc, s) => acc + (s.revenue ?? 0), 0);
  const arcs = positives.map((segment, index) => {
    const before = positives.slice(0, index).reduce((acc, s) => acc + (s.revenue ?? 0), 0);
    return {
      segment,
      ratio: arcTotal > 0 ? ((segment.revenue ?? 0) / arcTotal) * 100 : 0,
      // 12시 방향에서 시작해 시계 반대로 쌓는다
      offset: 25 - (arcTotal > 0 ? (before / arcTotal) * 100 : 0),
      color: colorOf.get(segment.code) ?? COLORS[0],
    };
  });
  const excluded = disclosed.filter((s) => (s.revenue ?? 0) <= 0);
  /*
   * 같은 사업부가 이름만 달리 두 번 오는 기록이 있어(삼성전자의 "DX 부문"과 "DX"), 위에서
   * 수치를 다 보여 준 부문이 아래에 "미공시" 로 또 붙었다. 이름을 맞춰 보고 걷어낸다.
   */
  const undisclosed = realUndisclosed(segments);

  /** 범례에 적는 비중. 공시값이 있으면 그대로 쓰고, 없으면 전체(음수 포함) 대비로 낸다 */
  const shareOf = (segment: ProfileSegment) =>
    segment.revenueShare ?? (sum > 0 ? ((segment.revenue ?? 0) / sum) * 100 : 0);

  const hoveredArc = arcs.find((arc) => arc.segment.code === hover) ?? null;

  return (
    <section
      aria-labelledby="segment-revenue-title"
      className="rounded-[var(--radius-card)] bg-white p-5 shadow-[var(--shadow-card)] ring-1 ring-slate-200/70"
    >
      <h2
        className="text-xl font-extrabold text-slate-950"
        id="segment-revenue-title"
      >
        사업부 매출
      </h2>

      <div className="mt-6 flex flex-col items-center gap-8 sm:flex-row">
        <div className="relative size-44 shrink-0">
          <svg
            aria-hidden="true"
            className="size-full"
            onMouseLeave={() => setHover(null)}
            viewBox="0 0 42 42"
          >
            {arcs.map(({ segment, ratio, offset, color }) => (
              <circle
                className="transition-[stroke-width] duration-150"
                cx="21"
                cy="21"
                data-testid="donut-arc"
                fill="none"
                key={segment.code}
                onMouseEnter={() => setHover(segment.code)}
                opacity={hover && hover !== segment.code ? 0.45 : 1}
                r={RADIUS}
                stroke={color}
                strokeDasharray={`${ratio} ${100 - ratio}`}
                strokeDashoffset={offset}
                strokeWidth={hover === segment.code ? 8 : 6}
              />
            ))}
          </svg>
          {/* 조각에 올리면 가운데 글씨가 그 부문 값으로 바뀐다 */}
          {(hoveredArc || totalRevenue !== null) && (
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center px-4 text-center">
              <span className="text-xs font-medium break-keep text-slate-500">
                {hoveredArc ? hoveredArc.segment.code : '전체 매출'}
              </span>
              <span className="text-sm font-extrabold text-slate-950 tabular-nums">
                {formatAmount(hoveredArc ? (hoveredArc.segment.revenue ?? 0) : (totalRevenue ?? 0))} 원
              </span>
              {hoveredArc && (
                <span className="text-xs font-semibold text-slate-500 tabular-nums">
                  {shareOf(hoveredArc.segment).toFixed(1)}%
                </span>
              )}
            </div>
          )}
        </div>

        <ul className="w-full min-w-0 flex-1 space-y-2.5">
          {/* 범례는 공시된 것을 그대로 다 적는다 (그래프에서 빠진 음수 항목도 값은 보여준다) */}
          {disclosed.map((segment) => (
            <li
              className="flex items-center gap-3 rounded-xl bg-slate-50 px-4 py-2.5 text-sm"
              key={segment.code}
            >
              <span
                aria-hidden="true"
                className="size-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: colorOf.get(segment.code) }}
              />
              <span className="min-w-0 flex-1 truncate font-bold text-slate-900">
                {segment.code}
              </span>
              <span className="font-medium text-slate-600">
                {formatAmount(segment.revenue ?? 0)} 원
              </span>
              <span className="w-14 text-right font-semibold text-slate-500">
                {shareOf(segment).toFixed(1)}%
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

      <p className="mt-5 text-xs break-keep text-slate-400">
        * 연결 기준 매출액
        {excluded.length > 0 && (
          <>
            {' · '}
            {excluded.map((s) => s.code).join(', ')}
            처럼 매출이 음수인 항목(연결 조정 등)은 그래프에서 빼고 비중만 적었습니다.
          </>
        )}
      </p>
    </section>
  );
}

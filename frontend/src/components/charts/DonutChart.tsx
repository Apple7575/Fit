import { useState, type ReactNode } from 'react';

export interface DonutSegment {
  label: string;
  value: number;
  color: string;
}

interface DonutChartProps {
  segments: DonutSegment[];
  /** 조각 위에 값도 함께 보여줄 때 쓰는 표기 (예: 매출액). 없으면 비율만 */
  formatValue?: (value: number) => string;
  /** 가운데 표시 (예: 총 이슈 수) */
  center?: ReactNode;
  /** 접근성용 제목 */
  title: string;
  size?: number;
}

/** 둘레가 정확히 100 이 되는 반지름 → stroke-dasharray 를 % 처럼 쓴다 */
const RADIUS = 15.915494309189535;

/**
 * 순수 SVG 도넛. 값이 0 이하인 조각은 그리지 않는다. 범례는 호출부가 그린다.
 * 각 조각에 data-testid="donut-arc" 를 둬 테스트에서 개수를 센다.
 */
export function DonutChart({ segments, center, title, size = 176, formatValue }: DonutChartProps) {
  const [hover, setHover] = useState<string | null>(null);
  const drawn = segments.filter((s) => s.value > 0);
  const sum = drawn.reduce((acc, s) => acc + s.value, 0);
  // 12시 방향(offset 25)에서 시작해 조각마다 자기 비율만큼 offset 을 줄여 이어 붙인다
  const arcs = drawn.reduce<Array<DonutSegment & { ratio: number; offset: number }>>(
    (acc, segment) => {
      const ratio = sum > 0 ? (segment.value / sum) * 100 : 0;
      const prev = acc[acc.length - 1];
      const offset = prev ? prev.offset - prev.ratio : 25;
      acc.push({ ...segment, ratio, offset });
      return acc;
    },
    [],
  );

  const hoveredArc = arcs.find((arc) => arc.label === hover) ?? null;

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg
        aria-label={title}
        className="size-full"
        onMouseLeave={() => setHover(null)}
        role="img"
        viewBox="0 0 42 42"
      >
        <circle cx="21" cy="21" fill="none" r={RADIUS} stroke="#f1f5f9" strokeWidth="6" />
        {arcs.map((arc) => (
          <circle
            className="transition-[stroke-width] duration-150"
            cx="21"
            cy="21"
            data-testid="donut-arc"
            fill="none"
            key={arc.label}
            onMouseEnter={() => setHover(arc.label)}
            opacity={hover && hover !== arc.label ? 0.45 : 1}
            r={RADIUS}
            stroke={arc.color}
            strokeDasharray={`${arc.ratio} ${100 - arc.ratio}`}
            strokeDashoffset={arc.offset}
            strokeWidth={hover === arc.label ? 8 : 6}
          >
            <title>{`${arc.label} ${arc.ratio.toFixed(1)}%`}</title>
          </circle>
        ))}
      </svg>
      {/* 조각에 올리면 가운데 글씨를 그 조각 값으로 바꿔 보여 준다 */}
      <div className="absolute inset-0 flex flex-col items-center justify-center px-4 text-center">
        {hoveredArc ? (
          <>
            <span className="text-[11px] font-bold break-keep text-slate-500">{hoveredArc.label}</span>
            <span className="mt-0.5 text-[17px] font-extrabold text-slate-950 tabular-nums">
              {hoveredArc.ratio.toFixed(1)}%
            </span>
            {formatValue && (
              <span className="text-[11px] font-semibold text-slate-500 tabular-nums">
                {formatValue(hoveredArc.value)}
              </span>
            )}
          </>
        ) : (
          center
        )}
      </div>
    </div>
  );
}

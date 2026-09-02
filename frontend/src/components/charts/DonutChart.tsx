import type { ReactNode } from 'react';

export interface DonutSegment {
  label: string;
  value: number;
  color: string;
}

interface DonutChartProps {
  segments: DonutSegment[];
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
export function DonutChart({ segments, center, title, size = 176 }: DonutChartProps) {
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

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg aria-label={title} className="size-full" role="img" viewBox="0 0 42 42">
        <circle cx="21" cy="21" fill="none" r={RADIUS} stroke="#f1f5f9" strokeWidth="6" />
        {arcs.map((arc) => (
          <circle
            cx="21"
            cy="21"
            data-testid="donut-arc"
            fill="none"
            key={arc.label}
            r={RADIUS}
            stroke={arc.color}
            strokeDasharray={`${arc.ratio} ${100 - arc.ratio}`}
            strokeDashoffset={arc.offset}
            strokeWidth="6"
          >
            <title>{`${arc.label} ${arc.ratio.toFixed(1)}%`}</title>
          </circle>
        ))}
      </svg>
      {center && (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          {center}
        </div>
      )}
    </div>
  );
}

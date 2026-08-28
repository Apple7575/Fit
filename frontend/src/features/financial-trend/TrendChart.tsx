import {
  useEffect,
  useId,
  useRef,
  useState,
  type PointerEvent,
} from 'react';
import { METRIC_LABELS } from '../../types/metrics';
import { formatMetricValue, metricUnitLabel } from '../../utils/formatMetric';
import { TREND_END_YEAR, TREND_START_YEAR, type TrendSeries } from './types';

interface TrendChartProps {
  /** 지표 키(series.key)로 표시명·단위를 정한다 */
  series: TrendSeries;
}

// viewBox 폭을 컨테이너 실제 픽셀 폭과 같게 맞춘다 (1 unit = 1px).
// 그래야 글자·선 굵기·마커가 화면 크기와 무관하게 규격(11px/2px/r4)을 유지하고, 넘치지도 않는다.
const DEFAULT_W = 640;
const VB_H = 280;
const PAD = { top: 20, right: 24, bottom: 36, left: 88 };
const PLOT_H = VB_H - PAD.top - PAD.bottom;

/** 컨테이너 폭 추적. jsdom 처럼 ResizeObserver 가 없으면 기본 폭을 쓴다. */
function useContainerWidth() {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(DEFAULT_W);

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(([entry]) => {
      const w = Math.round(entry.contentRect.width);
      if (w > 0) setWidth(w);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return { ref, width };
}

const YEARS = Array.from(
  { length: TREND_END_YEAR - TREND_START_YEAR + 1 },
  (_, i) => TREND_START_YEAR + i,
);


/** 0/1000/2000 식의 깔끔한 눈금. 값이 모두 양수면 0부터 시작한다. */
function niceTicks(values: number[], count = 4): number[] {
  if (values.length === 0) return [0, 1];
  const rawMin = Math.min(0, ...values);
  const rawMax = Math.max(0, ...values);
  const span = rawMax - rawMin || 1;
  const rough = span / count;
  const pow = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 5, 10].map((m) => m * pow).find((s) => s >= rough) ?? pow;
  const lo = Math.floor(rawMin / step) * step;
  const hi = Math.ceil(rawMax / step) * step;
  const ticks: number[] = [];
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(v);
  return ticks;
}

export function TrendChart({ series }: TrendChartProps) {
  const label = METRIC_LABELS[series.key];
  const unit = metricUnitLabel(series.key);
  const fmt = (v: number) => formatMetricValue(series.key, v);
  const [activeYear, setActiveYear] = useState<number | null>(null);
  const tooltipId = useId();
  const { ref: containerRef, width: VB_W } = useContainerWidth();
  const PLOT_W = VB_W - PAD.left - PAD.right;
  const xOf = (year: number) =>
    PAD.left + ((year - TREND_START_YEAR) / (YEARS.length - 1)) * PLOT_W;

  const valueByYear = new Map(series.points.map((p) => [p.year, p.value]));
  const known = YEARS.map((y) => valueByYear.get(y)).filter(
    (v): v is number => typeof v === 'number',
  );
  const ticks = niceTicks(known);
  const yMin = ticks[0];
  const yMax = ticks[ticks.length - 1];
  const yOf = (v: number) =>
    PAD.top + PLOT_H - ((v - yMin) / (yMax - yMin || 1)) * PLOT_H;

  // null 인 연도에서 선을 끊는다 (누락을 0으로 이어 그리지 않음).
  const segments: string[] = [];
  let current: string[] = [];
  for (const year of YEARS) {
    const v = valueByYear.get(year);
    if (typeof v === 'number') {
      current.push(`${xOf(year)},${yOf(v)}`);
    } else if (current.length) {
      segments.push(current.join(' '));
      current = [];
    }
  }
  if (current.length) segments.push(current.join(' '));

  const handlePointerMove = (event: PointerEvent<SVGSVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    if (rect.width === 0) return;
    const vx = ((event.clientX - rect.left) / rect.width) * VB_W;
    const index = Math.round(((vx - PAD.left) / PLOT_W) * (YEARS.length - 1));
    const clamped = Math.min(YEARS.length - 1, Math.max(0, index));
    setActiveYear(YEARS[clamped]);
  };

  const activeValue = activeYear === null ? undefined : valueByYear.get(activeYear);
  const activeText =
    activeValue === null || activeValue === undefined
      ? '미제공'
      : `${fmt(activeValue)} ${unit}`;

  return (
    <div className="relative" ref={containerRef}>
      <p
        className="mb-2 text-xs font-semibold text-slate-500"
        data-testid="y-axis-label"
      >
        {label} ({unit})
      </p>

      <svg
        aria-describedby={tooltipId}
        className="block w-full max-w-full overflow-visible"
        height={VB_H}
        data-testid="trend-svg"
        onPointerLeave={() => setActiveYear(null)}
        onPointerMove={handlePointerMove}
        role="img"
        aria-label={`${label} ${TREND_START_YEAR}~${TREND_END_YEAR}년 변화 그래프`}
        viewBox={`0 0 ${VB_W} ${VB_H}`}
      >
        {/* 가로 눈금선 + Y축 라벨 */}
        {ticks.map((t) => (
          <g key={t}>
            <line
              className="stroke-slate-200"
              strokeWidth={1}
              x1={PAD.left}
              x2={VB_W - PAD.right}
              y1={yOf(t)}
              y2={yOf(t)}
            />
            <text
              className="fill-slate-500 text-[11px]"
              dominantBaseline="middle"
              textAnchor="end"
              x={PAD.left - 10}
              y={yOf(t)}
            >
              {fmt(t)}
            </text>
          </g>
        ))}

        {/* X축 라벨 */}
        <g data-testid="x-axis">
          {YEARS.map((year) => (
            <text
              className="fill-slate-600 text-[12px] font-semibold"
              key={year}
              textAnchor="middle"
              x={xOf(year)}
              y={VB_H - PAD.bottom + 22}
            >
              {year}
            </text>
          ))}
        </g>

        {/* 크로스헤어 */}
        {activeYear !== null && (
          <line
            className="stroke-slate-400"
            strokeWidth={1}
            x1={xOf(activeYear)}
            x2={xOf(activeYear)}
            y1={PAD.top}
            y2={PAD.top + PLOT_H}
          />
        )}

        {/* 선 (누락 연도에서 끊김) */}
        {segments.map((points) => (
          <polyline
            className="stroke-blue-600"
            fill="none"
            key={points}
            points={points}
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
          />
        ))}

        {/* 마커: 키보드 포커스 가능, 2px 흰 링 */}
        {YEARS.map((year) => {
          const v = valueByYear.get(year);
          if (typeof v !== 'number') return null;
          const isActive = activeYear === year;
          return (
            <circle
              aria-label={`${year}년 ${fmt(v)} ${unit}`}
              className="cursor-pointer fill-blue-600 stroke-white outline-none focus-visible:stroke-blue-300"
              cx={xOf(year)}
              cy={yOf(v)}
              key={year}
              onBlur={() => setActiveYear(null)}
              onFocus={() => setActiveYear(year)}
              r={isActive ? 6 : 4}
              role="button"
              strokeWidth={2}
              tabIndex={0}
            />
          );
        })}
      </svg>

      {/* 툴팁: 값이 먼저, 연도가 뒤 */}
      <div
        aria-live="polite"
        className={`pointer-events-none absolute -translate-x-1/2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-md ${
          activeYear === null ? 'invisible' : ''
        }`}
        id={tooltipId}
        role={activeYear === null ? undefined : 'tooltip'}
        style={{
          left: activeYear === null ? 0 : `${(xOf(activeYear) / VB_W) * 100}%`,
          top: 0,
        }}
      >
        {activeYear !== null && (
          <>
            <span className="block font-bold text-slate-950">{activeText}</span>
            <span className="text-slate-500">{activeYear}년</span>
          </>
        )}
      </div>

      {/* 표 뷰: 스크린리더·복사용 */}
      <table className="sr-only" aria-label={`${label} 연도별 값`}>
        <thead>
          <tr>
            <th scope="col">연도</th>
            <th scope="col">{label} ({unit})</th>
          </tr>
        </thead>
        <tbody>
          {YEARS.map((year) => {
            const v = valueByYear.get(year);
            return (
              <tr key={year}>
                <th scope="row">{year}</th>
                <td>{typeof v === 'number' ? fmt(v) : '미제공'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

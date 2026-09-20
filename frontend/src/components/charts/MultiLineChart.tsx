import { useId, useRef } from 'react';
import { niceTicks, useContainerWidth } from './chartMath';
import { ChartTooltip, useChartHover } from './ChartTooltip';

export interface LineSeries {
  label: string;
  color: string;
  /** 강조 선 (조회 기업 등) — 더 굵게 */
  emphasis?: boolean;
  /** x 라벨 순서대로. 없으면 null → 선이 끊긴다 */
  points: Array<{ x: string; y: number | null }>;
}

interface MultiLineChartProps {
  series: LineSeries[];
  formatValue: (v: number) => string;
  /** 접근성용 제목 */
  title: string;
  valueName: string;
  height?: number;
}

const PAD = { top: 24, right: 20, bottom: 32, left: 64 };

/**
 * 여러 기업을 색이 다른 꺾은선으로 겹쳐 그린다. 값이 없는 해는 점을 찍지 않고 선을 끊는다
 * (0 으로 잇지 않음). 범례는 아래에, 스크린리더용 표를 함께 제공한다.
 */
export function MultiLineChart({
  series,
  formatValue,
  title,
  valueName,
  height = 280,
}: MultiLineChartProps) {
  const tableId = useId();
  const { ref, width: W } = useContainerWidth();
  const svgRef = useRef<SVGSVGElement>(null);
  const hover = useChartHover(svgRef);
  const H = height;
  const PLOT_W = W - PAD.left - PAD.right;
  const PLOT_H = H - PAD.top - PAD.bottom;
  const xLabels = series[0]?.points.map((p) => p.x) ?? [];
  const xOf = (i: number) =>
    xLabels.length > 1 ? PAD.left + (i / (xLabels.length - 1)) * PLOT_W : PAD.left + PLOT_W / 2;

  const all = series.flatMap((s) => s.points.map((p) => p.y)).filter((v): v is number => v !== null);
  const ticks = niceTicks(all);
  const vMin = ticks[0];
  const vMax = ticks[ticks.length - 1];
  const yOf = (v: number) => PAD.top + PLOT_H - ((v - vMin) / (vMax - vMin || 1)) * PLOT_H;

  const segmentsOf = (s: LineSeries) => {
    const out: string[] = [];
    let cur: string[] = [];
    s.points.forEach((p, i) => {
      if (p.y !== null) cur.push(`${xOf(i)},${yOf(p.y)}`);
      else if (cur.length) {
        out.push(cur.join(' '));
        cur = [];
      }
    });
    if (cur.length) out.push(cur.join(' '));
    return out;
  };

  /** 어느 점 가까이인지. 가로로 가깝고, 그 해의 어떤 선 위에라도 세로로 가까워야 한다 */
  const hitTest = (x: number, y: number) => {
    let best: { index: number; dist: number } | null = null;
    xLabels.forEach((_, i) => {
      if (Math.abs(x - xOf(i)) > 22) return;
      series.forEach((s) => {
        const v = s.points[i]?.y;
        if (v === null || v === undefined) return;
        const dy = Math.abs(y - yOf(v));
        if (dy <= 26 && (best === null || dy < best.dist)) best = { index: i, dist: dy };
      });
    });
    return best === null ? null : (best as { index: number; dist: number }).index;
  };

  return (
    <div className="relative" ref={ref}>
      <svg
        aria-describedby={tableId}
        aria-label={title}
        className="block w-full max-w-full overflow-visible"
        data-testid="multi-line-chart"
        height={H}
        onMouseLeave={hover.clear}
        onMouseMove={(e) => hover.track(e, hitTest)}
        ref={svgRef}
        role="img"
        viewBox={`0 0 ${W} ${H}`}
      >
        {hover.point && (
          <line
            className="stroke-slate-400"
            strokeDasharray="3 3"
            strokeWidth={1}
            x1={xOf(hover.point.index)}
            x2={xOf(hover.point.index)}
            y1={PAD.top}
            y2={PAD.top + PLOT_H}
          />
        )}
        {ticks.map((t) => (
          <g key={t}>
            <line
              className="stroke-slate-200"
              strokeDasharray={t === 0 ? undefined : '3 3'}
              strokeWidth={1}
              x1={PAD.left}
              x2={W - PAD.right}
              y1={yOf(t)}
              y2={yOf(t)}
            />
            <text
              className="fill-slate-500 text-[11px]"
              dominantBaseline="middle"
              textAnchor="end"
              x={PAD.left - 8}
              y={yOf(t)}
            >
              {formatValue(t)}
            </text>
          </g>
        ))}
        {xLabels.map((label, i) => (
          <text
            className="fill-slate-600 text-[12px] font-semibold"
            key={label}
            textAnchor="middle"
            x={xOf(i)}
            y={H - PAD.bottom + 22}
          >
            {label}
          </text>
        ))}

        {series.map((s) => (
          <g data-series={s.label} data-testid="line-series" key={s.label}>
            {segmentsOf(s).map((pts) => (
              <polyline
                fill="none"
                key={pts}
                points={pts}
                stroke={s.color}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={s.emphasis ? 3 : 2}
              />
            ))}
            {s.points.map((p, i) =>
              p.y === null ? null : (
                <circle
                  cx={xOf(i)}
                  cy={yOf(p.y)}
                  data-testid="line-point"
                  fill="#fff"
                  key={p.x}
                  r={s.emphasis ? 4 : 3}
                  stroke={s.color}
                  strokeWidth={2}
                >
                  <title>{`${s.label} ${p.x}: ${formatValue(p.y)}`}</title>
                </circle>
              ),
            )}
          </g>
        ))}

      </svg>

      {hover.point && (
        <ChartTooltip
          rows={series.map((s) => {
            const y = s.points[hover.point!.index]?.y;
            return {
              label: s.label,
              value: y === null || y === undefined ? '미제공' : formatValue(y),
              color: s.color,
              emphasis: s.emphasis,
            };
          })}
          title={`${xLabels[hover.point.index]} · ${valueName}`}
          width={W}
          x={hover.point.x}
          y={hover.point.y}
        />
      )}

      <ul aria-label="범례" className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs font-semibold text-slate-600">
        {series.map((s) => {
          const empty = s.points.every((p) => p.y === null);
          return (
            <li className="inline-flex items-center gap-1.5" key={s.label}>
              <span
                aria-hidden="true"
                className="inline-block h-0.5 w-4 rounded-full"
                style={{ backgroundColor: s.color, height: s.emphasis ? 3 : 2 }}
              />
              <span className={s.emphasis ? 'font-extrabold text-slate-900' : ''}>{s.label}</span>
              {empty && <span className="text-slate-400">(미제공)</span>}
            </li>
          );
        })}
      </ul>

      <table className="sr-only" id={tableId}>
        <caption>{title}</caption>
        <thead>
          <tr>
            <th scope="col">구분</th>
            {xLabels.map((label) => (
              <th key={label} scope="col">
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {series.map((s) => (
            <tr key={s.label}>
              <th scope="row">
                {s.label} ({valueName})
              </th>
              {s.points.map((p) => (
                <td key={p.x}>{p.y === null ? '미제공' : formatValue(p.y)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

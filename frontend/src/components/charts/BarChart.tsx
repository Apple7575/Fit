import { useId } from 'react';
import { niceTicks, useContainerWidth } from './chartMath';

export interface BarChartItem {
  label: string;
  /** 없으면 null (0과 구분) → 점선 자리 + 미제공 */
  value: number | null;
  /** 강조 막대 (조회 기업 등) */
  highlight?: boolean;
}

interface BarChartProps {
  items: BarChartItem[];
  formatValue: (v: number) => string;
  /** 접근성용 제목 */
  title: string;
  /** 표 헤더용 값 이름 */
  valueName: string;
  height?: number;
}

const PAD = { top: 28, right: 16, bottom: 36, left: 56 };

/**
 * 세로 막대 차트. 강조 항목은 진한 파랑, 나머지는 연한 파랑, 음수는 손실 색.
 * 값 없는 항목은 점선 자리에 "미제공". 스크린리더용 표를 함께 제공한다.
 */
export function BarChart({
  items,
  formatValue,
  title,
  valueName,
  height = 280,
}: BarChartProps) {
  const tableId = useId();
  const { ref, width: W } = useContainerWidth();
  const H = height;
  const PLOT_W = W - PAD.left - PAD.right;
  const PLOT_H = H - PAD.top - PAD.bottom;
  const slot = items.length > 0 ? PLOT_W / items.length : PLOT_W;
  const barW = Math.min(64, slot * 0.5);
  const xCenter = (i: number) => PAD.left + slot * i + slot / 2;

  const values = items.map((it) => it.value).filter((v): v is number => v !== null);
  const ticks = niceTicks(values);
  const vMin = ticks[0];
  const vMax = ticks[ticks.length - 1];
  const yOf = (v: number) => PAD.top + PLOT_H - ((v - vMin) / (vMax - vMin || 1)) * PLOT_H;

  return (
    <div ref={ref}>
      <svg
        aria-describedby={tableId}
        aria-label={title}
        className="block w-full max-w-full overflow-visible"
        data-testid="bar-chart"
        height={H}
        role="img"
        viewBox={`0 0 ${W} ${H}`}
      >
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

        {items.map((it, i) => {
          const x = xCenter(i);
          return (
            <g key={it.label}>
              {it.value === null ? (
                <>
                  <rect
                    className="fill-none stroke-slate-300"
                    height={PLOT_H}
                    rx={4}
                    strokeDasharray="4 4"
                    width={barW}
                    x={x - barW / 2}
                    y={PAD.top}
                  />
                  <text
                    className="fill-slate-400 text-[11px] font-semibold"
                    textAnchor="middle"
                    x={x}
                    y={PAD.top + PLOT_H / 2}
                  >
                    미제공
                  </text>
                </>
              ) : (
                <>
                  <rect
                    className={
                      it.value < 0
                        ? 'fill-rose-400'
                        : it.highlight
                          ? 'fill-blue-600'
                          : 'fill-blue-200'
                    }
                    data-highlight={it.highlight ? 'true' : undefined}
                    data-testid="bar"
                    height={Math.max(2, Math.abs(yOf(it.value) - yOf(0)))}
                    rx={4}
                    width={barW}
                    x={x - barW / 2}
                    y={Math.min(yOf(it.value), yOf(0))}
                  />
                  <text
                    className="fill-slate-700 text-[11px] font-bold"
                    textAnchor="middle"
                    x={x}
                    y={Math.min(yOf(it.value), yOf(0)) - 6}
                  >
                    {formatValue(it.value)}
                  </text>
                </>
              )}
              <text
                className={`text-[12px] font-semibold ${
                  it.highlight ? 'fill-blue-700' : 'fill-slate-600'
                }`}
                textAnchor="middle"
                x={x}
                y={H - PAD.bottom + 22}
              >
                {it.label}
              </text>
            </g>
          );
        })}
      </svg>

      <table className="sr-only" id={tableId}>
        <caption>{title}</caption>
        <thead>
          <tr>
            <th scope="col">구분</th>
            <th scope="col">{valueName}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it) => (
            <tr key={it.label}>
              <th scope="row">{it.label}</th>
              <td>{it.value === null ? '미제공' : formatValue(it.value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

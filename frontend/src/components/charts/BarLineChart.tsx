import { useId } from 'react';
import { niceTicks, symmetricTicks, useContainerWidth } from './chartMath';

export interface BarLinePoint {
  label: string;
  /** 막대 값. 없으면 null (0과 구분) */
  value: number | null;
  /** 꺾은선 값(%). 없으면 null */
  rate: number | null;
}

interface BarLineChartProps {
  points: BarLinePoint[];
  /** 막대 값 표기 (축·막대 위 라벨) */
  formatValue: (v: number) => string;
  /** 접근성용 제목과 범례 이름 */
  title: string;
  valueName: string;
  rateName?: string;
}

const H = 340;
const PAD = { top: 30, right: 56, bottom: 36, left: 64 };
const PLOT_H = H - PAD.top - PAD.bottom;
/** 증가율 꺾은선이 쓰는 위 띠. 막대와 같은 자리에 그리면 선·점·글씨가 막대에 묻힌다 */
const RATE_H = 84;
/** 두 띠 사이 여백. 막대 위 값 글씨가 여기 들어간다 */
const BAND_GAP = 22;

/**
 * 값은 아래 띠에 막대로, 증가율(%)은 위 띠에 꺾은선으로 — 가로축만 공유하고 자리는 나눈다.
 * 값이 없는 연도는 막대를 그리지 않고 "미제공"으로 표시하며, 선은 그 지점에서 끊는다.
 * 스크린리더용 표를 함께 제공한다.
 */
export function BarLineChart({
  points,
  formatValue,
  title,
  valueName,
  rateName = '증가율',
}: BarLineChartProps) {
  const tableId = useId();
  const { ref, width: W } = useContainerWidth();
  const PLOT_W = W - PAD.left - PAD.right;
  const slot = points.length > 0 ? PLOT_W / points.length : PLOT_W;
  const barW = Math.min(56, slot * 0.42);
  const xCenter = (i: number) => PAD.left + slot * i + slot / 2;

  const values = points.map((p) => p.value).filter((v): v is number => v !== null);
  const rates = points.map((p) => p.rate).filter((v): v is number => v !== null);
  const hasRates = rates.length > 0;

  // 위 띠는 증가율, 아래 띠는 값. 증가율이 없으면 막대가 전체를 쓴다
  const rateH = hasRates ? RATE_H : 0;
  const barTop = PAD.top + rateH + (hasRates ? BAND_GAP : 0);
  const barH = PAD.top + PLOT_H - barTop;

  const vTicks = niceTicks(values);
  const vMin = vTicks[0];
  const vMax = vTicks[vTicks.length - 1];
  const yOf = (v: number) => barTop + barH - ((v - vMin) / (vMax - vMin || 1)) * barH;
  const rTicks = hasRates ? symmetricTicks(rates) : [];
  const rMax = hasRates ? rTicks[rTicks.length - 1] : 1;
  const yOfRate = (r: number) => PAD.top + rateH / 2 - (r / (rMax || 1)) * (rateH / 2);

  // 증가율 선: null 에서 끊는다
  const segments: string[] = [];
  let current: string[] = [];
  points.forEach((p, i) => {
    if (p.rate !== null) current.push(`${xCenter(i)},${yOfRate(p.rate)}`);
    else if (current.length) {
      segments.push(current.join(' '));
      current = [];
    }
  });
  if (current.length) segments.push(current.join(' '));

  return (
    <div ref={ref}>
      <p className="mb-3 flex flex-wrap gap-4 text-xs font-semibold text-slate-500">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="inline-block h-2.5 w-4 rounded-sm bg-blue-600" />
          {valueName}(아래)
        </span>
        {hasRates && (
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden="true" className="inline-block size-2.5 rounded-full border-2 border-sky-400 bg-white" />
            {rateName}(위)
          </span>
        )}
      </p>

      <svg
        aria-describedby={tableId}
        aria-label={title}
        className="block w-full max-w-full overflow-visible"
        data-testid="bar-line-chart"
        height={H}
        role="img"
        viewBox={`0 0 ${W} ${H}`}
      >
        {hasRates && (
          <rect
            className="fill-slate-50"
            height={rateH}
            rx={10}
            width={W - PAD.left - PAD.right}
            x={PAD.left}
            y={PAD.top}
          />
        )}
        {vTicks.map((t) => (
          <g key={`v-${t}`}>
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
        {hasRates && (
          <g>
            <line
              className="stroke-slate-300"
              strokeDasharray="3 3"
              strokeWidth={1}
              x1={PAD.left}
              x2={W - PAD.right}
              y1={yOfRate(0)}
              y2={yOfRate(0)}
            />
            {[rTicks[rTicks.length - 1], 0].map((t) => (
              <text
                className="fill-slate-400 text-[11px]"
                dominantBaseline="middle"
                key={`r-${t}`}
                textAnchor="start"
                x={W - PAD.right + 8}
                y={yOfRate(t)}
              >
                {t > 0 ? '+' : ''}
                {t}%
              </text>
            ))}
          </g>
        )}

        {points.map((p, i) => {
          const x = xCenter(i);
          return (
            <g key={p.label}>
              {p.value === null ? (
                <>
                  <rect
                    className="fill-none stroke-slate-300"
                    height={barH}
                    rx={4}
                    strokeDasharray="4 4"
                    width={barW}
                    x={x - barW / 2}
                    y={barTop}
                  />
                  <text
                    className="fill-slate-400 text-[11px] font-semibold"
                    textAnchor="middle"
                    x={x}
                    y={barTop + barH / 2}
                  >
                    미제공
                  </text>
                </>
              ) : (
                <>
                  <rect
                    className={p.value < 0 ? 'fill-rose-400' : 'fill-blue-600'}
                    data-testid="bar"
                    height={Math.max(2, Math.abs(yOf(p.value) - yOf(0)))}
                    rx={4}
                    width={barW}
                    x={x - barW / 2}
                    y={Math.min(yOf(p.value), yOf(0))}
                  />
                  <text
                    className="fill-slate-700 text-[11px] font-bold"
                    textAnchor="middle"
                    x={x}
                    y={Math.min(yOf(p.value), yOf(0)) - 6}
                  >
                    {formatValue(p.value)}
                  </text>
                </>
              )}
              <text
                className="fill-slate-600 text-[12px] font-semibold"
                textAnchor="middle"
                x={x}
                y={H - PAD.bottom + 22}
              >
                {p.label}
              </text>
            </g>
          );
        })}

        {segments.map((pts) => (
          <polyline
            className="stroke-sky-400"
            fill="none"
            key={pts}
            points={pts}
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
          />
        ))}
        {points.map((p, i) =>
          p.rate === null ? null : (
            <g key={`pt-${p.label}`}>
              <circle
                className="fill-white stroke-sky-400"
                cx={xCenter(i)}
                cy={yOfRate(p.rate)}
                data-testid="rate-point"
                r={4}
                strokeWidth={2}
              />
              <text
                className="fill-sky-700 text-[11px] font-bold"
                textAnchor="middle"
                x={xCenter(i)}
                y={yOfRate(p.rate) - 9}
              >
                {p.rate > 0 ? '+' : ''}
                {p.rate.toFixed(1)}%
              </text>
            </g>
          ),
        )}
      </svg>

      <table className="sr-only" id={tableId}>
        <caption>{title}</caption>
        <thead>
          <tr>
            <th scope="col">구분</th>
            <th scope="col">{valueName}</th>
            <th scope="col">{rateName}</th>
          </tr>
        </thead>
        <tbody>
          {points.map((p) => (
            <tr key={p.label}>
              <th scope="row">{p.label}</th>
              <td>{p.value === null ? '미제공' : formatValue(p.value)}</td>
              <td>{p.rate === null ? '미제공' : `${p.rate > 0 ? '+' : ''}${p.rate.toFixed(1)}%`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

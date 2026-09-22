import { useState, type MouseEvent as ReactMouseEvent, type RefObject } from 'react';

export interface TooltipRow {
  label: string;
  value: string;
  /** 계열 색 점. 없으면 점을 그리지 않는다 */
  color?: string;
  /** 굵게 (조회 기업 등) */
  emphasis?: boolean;
}

/** 마우스가 이 자리(차트 좌표)에서 어느 지점을 가리키는지. 가리키는 게 없으면 null */
export type HitTest = (x: number, y: number) => number | null;

interface Hover {
  index: number;
  /** 차트 좌표 기준 커서 위치 */
  x: number;
  y: number;
}

/**
 * 그래프 위 마우스 추적.
 *
 * <p>값 상자는 커서를 따라다녀야 하고, 지점(막대·점)을 벗어나면 사라져야 한다.
 * 어디까지를 "그 지점 위"로 볼지는 차트마다 다르므로 판정은 hit 함수가 한다.
 */
export function useChartHover(svgRef: RefObject<SVGSVGElement | null>) {
  const [point, setPoint] = useState<Hover | null>(null);

  const track = (event: ReactMouseEvent<SVGSVGElement>, hit: HitTest) => {
    const el = svgRef.current;
    if (!el) return;
    const box = el.getBoundingClientRect();
    if (box.width === 0 || box.height === 0) return;
    // viewBox 좌표로 바꾼다 (컨테이너 너비에 맞춰 그리므로 보통 1:1 이다)
    const vb = el.viewBox.baseVal;
    const scaleX = vb.width ? vb.width / box.width : 1;
    const scaleY = vb.height ? vb.height / box.height : 1;
    const x = (event.clientX - box.left) * scaleX;
    const y = (event.clientY - box.top) * scaleY;
    const index = hit(x, y);
    setPoint(index === null ? null : { index, x, y });
  };

  return { point, track, clear: () => setPoint(null) };
}

/**
 * 커서 바로 위에 뜨는 값 상자.
 *
 * <p>차트는 viewBox 를 컨테이너 너비에 맞춰 그리므로 좌표를 그대로 써서 HTML 상자를 올릴 수 있다
 * (SVG 안에 글씨를 그리면 차트 밖으로 잘린다). 양 끝에서는 기준점을 옮겨 화면 밖으로 나가지 않게 한다.
 */
export function ChartTooltip({
  x,
  y,
  width,
  title,
  rows,
}: {
  /** 커서 x (차트 좌표) */
  x: number;
  /** 커서 y (차트 좌표) */
  y: number;
  /** 차트 전체 너비. 끝에서 잘리지 않게 쓴다 */
  width: number;
  title: string;
  rows: TooltipRow[];
}) {
  const nearLeft = x < 92;
  const nearRight = width - x < 92;
  const alignX = nearLeft ? '0%' : nearRight ? '-100%' : '-50%';

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute z-10 min-w-[116px] rounded-xl bg-slate-900/92 px-3 py-2 text-white shadow-lg"
      // 커서 바로 위. 위쪽이 좁으면 아래로 내려 단다
      style={{
        left: x,
        top: y,
        transform: `translate(${alignX}, ${y < 72 ? '14px' : 'calc(-100% - 14px)'})`,
      }}
    >
      <p className="text-[11px] font-bold text-white/60">{title}</p>
      <ul className="mt-1 space-y-0.5">
        {rows.map((row) => (
          <li className="flex items-center gap-2 text-[12px] whitespace-nowrap" key={row.label}>
            {row.color && (
              <span className="inline-block size-2 shrink-0 rounded-full" style={{ backgroundColor: row.color }} />
            )}
            <span className="text-white/70">{row.label}</span>
            <span className={`ml-auto tabular-nums ${row.emphasis ? 'font-extrabold' : 'font-semibold'}`}>
              {row.value}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

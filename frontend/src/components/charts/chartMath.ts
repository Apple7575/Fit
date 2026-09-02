import { useEffect, useRef, useState } from 'react';

/** 0/1000/2000 식의 깔끔한 눈금. 값이 모두 양수면 0부터 시작한다. */
export function niceTicks(values: number[], count = 4): number[] {
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

/** 0 을 가운데 둔 대칭 눈금 (-M..M). 증가율 축처럼 음수·양수를 같이 보일 때. */
export function symmetricTicks(values: number[], halfCount = 2): number[] {
  const maxAbs = Math.max(1, ...values.map((v) => Math.abs(v)));
  const rough = maxAbs / halfCount;
  const pow = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 5, 10].map((m) => m * pow).find((s) => s >= rough) ?? pow;
  const top = Math.ceil(maxAbs / step) * step;
  const ticks: number[] = [];
  for (let v = -top; v <= top + step / 2; v += step) ticks.push(v);
  return ticks;
}

/**
 * 컨테이너 폭 추적. viewBox 폭을 실제 픽셀 폭과 같게 맞춰 글자·선 굵기가 화면 크기와
 * 무관하게 유지되게 한다. jsdom 처럼 ResizeObserver 가 없으면 기본 폭을 쓴다.
 */
export function useContainerWidth(defaultWidth = 640) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(defaultWidth);

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

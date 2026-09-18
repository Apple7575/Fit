interface RangeBarProps {
  label: string;
  /** 측정값 */
  value: number;
  /** 화면에 쓸 표기 (예: "312 음절/분") */
  display: string;
  /** 막대 전체 범위 */
  scaleMax: number;
  /** 적정 구간 */
  okFrom: number;
  okTo: number;
  /** 값이 적정 구간 밖일 때 보여줄 한 줄 */
  hint?: string;
}

/**
 * 점수 대신 "적정 구간 안/밖"만 보여주는 막대.
 * 회색 막대 위에 초록 구간을 깔고, 측정값 위치에 점을 찍는다. 기준은 delivery.ts 의 임계값이다.
 */
export function RangeBar({ label, value, display, scaleMax, okFrom, okTo, hint }: RangeBarProps) {
  const pct = (v: number) => `${Math.max(0, Math.min(100, (v / scaleMax) * 100))}%`;
  const ok = value >= okFrom && value <= okTo;

  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[13px] font-semibold text-slate-700">{label}</span>
        <span
          className={`text-[13px] font-bold tabular-nums ${ok ? 'text-emerald-700' : 'text-amber-700'}`}
        >
          {display}
          <span className="ml-1 text-[11px] font-semibold">{ok ? '적정' : '확인'}</span>
        </span>
      </div>
      <div aria-hidden="true" className="relative mt-2 h-2.5 rounded-full bg-slate-100">
        <span
          className="absolute inset-y-0 rounded-full bg-emerald-200"
          style={{ left: pct(okFrom), width: `calc(${pct(okTo)} - ${pct(okFrom)})` }}
        />
        <span
          className={`absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-white ${
            ok ? 'bg-emerald-600' : 'bg-amber-500'
          }`}
          style={{ left: pct(value) }}
        />
      </div>
      <p className="mt-1.5 text-[11px] text-slate-400">
        적정 {okFrom}–{okTo}
        {!ok && hint ? ` · ${hint}` : ''}
      </p>
    </div>
  );
}

export interface MiniBarPoint {
  label: string;
  /** 없으면 null — 0 으로 그리지 않고 빈 자리로 둔다 */
  value: number | null;
}

interface MiniBarsProps {
  points: MiniBarPoint[];
  /** 접근성용 제목 */
  title: string;
  /** 값 표기 (스크린리더 표) */
  formatValue: (v: number) => string;
  /** 화면에 들어올 때 아래서 자라나게 (조상 요소의 data-inview 를 따른다) */
  animated?: boolean;
}

/**
 * 요약 카드용 작은 막대. 축·눈금 없이 높이 비율만 보여주고 마지막 해를 강조한다.
 * 값이 없는 해는 점선 자리로 남긴다. 숫자는 스크린리더용 표로 따로 제공한다.
 */
export function MiniBars({ points, title, formatValue, animated = false }: MiniBarsProps) {
  const values = points.map((p) => p.value).filter((v): v is number => v !== null);
  const max = Math.max(...values, 0);
  const last = points.length - 1;

  return (
    <div>
      <div aria-hidden="true" className="flex h-16 items-end gap-1.5">
        {points.map((p, i) => {
          if (p.value === null) {
            return (
              <div
                className="flex-1 self-stretch rounded-md border border-dashed border-slate-200"
                key={p.label}
              />
            );
          }
          const ratio = max > 0 ? Math.max(p.value, 0) / max : 0;
          return (
            <div className="flex flex-1 items-end self-stretch" key={p.label}>
              <div
                className={`w-full rounded-md ${animated ? 'grow-y' : ''} ${
                  i === last ? 'bg-blue-600' : 'bg-blue-200'
                }`}
                style={{ height: `${Math.max(ratio * 100, 4)}%`, '--grow-delay': `${i * 90}ms` } as never}
              />
            </div>
          );
        })}
      </div>
      <div aria-hidden="true" className="mt-1 flex gap-1.5">
        {points.map((p, i) => (
          <span
            className={`flex-1 text-center text-[10px] font-semibold tabular-nums ${
              i === last ? 'text-blue-700' : 'text-slate-400'
            }`}
            key={p.label}
          >
            {p.label}
          </span>
        ))}
      </div>
      <table className="sr-only">
        <caption>{title}</caption>
        <tbody>
          {points.map((p) => (
            <tr key={p.label}>
              <th scope="row">{p.label}</th>
              <td>{p.value === null ? '미제공' : formatValue(p.value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

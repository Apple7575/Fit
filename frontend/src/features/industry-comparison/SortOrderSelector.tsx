import { useId } from 'react';
import type { SortOrder } from './types';

const OPTIONS: Array<{ value: SortOrder; label: string }> = [
  { value: 'desc', label: '값이 큰 순' },
  { value: 'asc', label: '값이 작은 순' },
];

interface SortOrderSelectorProps {
  value: SortOrder;
  onChange: (order: SortOrder) => void;
}

/**
 * 정렬 방향을 고르는 라디오 그룹.
 * MetricSelector 와 같은 pill 모양이지만 실제 <input type="radio"> 라 방향키 이동이 동작한다.
 */
export function SortOrderSelector({ value, onChange }: SortOrderSelectorProps) {
  const name = useId();

  return (
    <fieldset className="flex flex-wrap gap-2">
      <legend className="sr-only">정렬 기준 선택</legend>
      {OPTIONS.map((option) => {
        const checked = option.value === value;

        return (
          <label
            className={`cursor-pointer rounded-full border px-3.5 py-1.5 text-sm font-semibold transition select-none has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-blue-300 ${
              checked
                ? 'border-slate-900 bg-slate-900 text-white'
                : 'border-slate-300 bg-white text-slate-600 hover:border-slate-400 hover:text-slate-950'
            }`}
            key={option.value}
          >
            <input
              checked={checked}
              className="sr-only"
              name={name}
              onChange={() => onChange(option.value)}
              type="radio"
              value={option.value}
            />
            {option.label}
          </label>
        );
      })}
    </fieldset>
  );
}

import { useId } from 'react';

export interface PillOption<K extends string> {
  value: K;
  label: string;
  /** 선택은 되지만 데이터가 없음을 알리는 보조 표시 (예: "미제공") */
  hint?: string;
}

interface PillRadioGroupProps<K extends string> {
  value: K;
  onChange: (value: K) => void;
  /** 그룹 레이블 (스크린리더용) */
  label: string;
  options: ReadonlyArray<PillOption<K>>;
}

/**
 * pill 모양 라디오 그룹. 실제 <input type="radio"> 라 방향키 이동·폼 시맨틱이 그대로 동작한다.
 * financial-trend/MetricSelector 와 같은 모양이며, 지표 카탈로그에 묶이지 않은 범용판이다.
 */
export function PillRadioGroup<K extends string>({
  value,
  onChange,
  label,
  options,
}: PillRadioGroupProps<K>) {
  const name = useId();

  return (
    <fieldset className="flex flex-wrap gap-2">
      <legend className="sr-only">{label}</legend>
      {options.map((option) => {
        const checked = option.value === value;
        return (
          <label
            className={`cursor-pointer rounded-full border px-3.5 py-1.5 text-sm font-semibold transition select-none has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-blue-300 ${
              checked
                ? 'border-blue-600 bg-blue-600 text-white'
                : option.hint
                  ? 'border-dashed border-slate-300 bg-white text-slate-400 hover:border-slate-400'
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
            {option.hint && (
              <span className="ml-1 text-xs font-medium opacity-80">
                ({option.hint})
              </span>
            )}
          </label>
        );
      })}
    </fieldset>
  );
}

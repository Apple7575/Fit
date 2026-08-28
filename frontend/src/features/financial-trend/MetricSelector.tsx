import { useId } from 'react';
import { METRIC_KEYS, METRIC_LABELS, type MetricKey } from '../../types/metrics';

interface MetricSelectorProps {
  value: MetricKey;
  onChange: (key: MetricKey) => void;
  /** 그룹 레이블 (스크린리더용). 기본 "지표 선택" */
  label?: string;
  /** 보여줄 지표. 생략하면 6개 전부 (산업 비교처럼 일부만 지원하는 곳에서 좁힌다) */
  options?: readonly MetricKey[];
}

/**
 * 지표 6개 중 하나를 고르는 라디오 그룹. pill 모양이지만 실제 <input type="radio"> 라
 * 방향키 이동·폼 시맨틱이 그대로 동작한다. 선택 항목은 색·굵기·aria-checked 로 구분.
 */
export function MetricSelector({
  value,
  onChange,
  label = '지표 선택',
  options = METRIC_KEYS,
}: MetricSelectorProps) {
  const name = useId();

  return (
    <fieldset className="flex flex-wrap gap-2">
      <legend className="sr-only">{label}</legend>
      {options.map((key) => {
        const checked = key === value;
        return (
          <label
            className={`cursor-pointer rounded-full border px-3.5 py-1.5 text-sm font-semibold transition select-none has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-blue-300 ${
              checked
                ? 'border-blue-600 bg-blue-600 text-white'
                : 'border-slate-300 bg-white text-slate-600 hover:border-slate-400 hover:text-slate-950'
            }`}
            key={key}
          >
            <input
              checked={checked}
              className="sr-only"
              name={name}
              onChange={() => onChange(key)}
              type="radio"
              value={key}
            />
            {METRIC_LABELS[key]}
          </label>
        );
      })}
    </fieldset>
  );
}

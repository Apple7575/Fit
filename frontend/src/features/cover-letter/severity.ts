import type { Severity } from './types';

/** 심각도별 표시 토큰. 하이라이트·칩·카드 강조에 공통으로 쓴다. */
export const SEVERITY_STYLE: Record<
  Severity,
  { label: string; dot: string; chip: string; mark: string; markActive: string; cardRing: string }
> = {
  WARNING: {
    label: '개선 필요',
    dot: 'bg-rose-500',
    chip: 'bg-rose-100 text-rose-700',
    mark: 'bg-rose-200/70 decoration-rose-400',
    markActive: 'bg-rose-300 ring-2 ring-rose-400',
    cardRing: 'ring-rose-300 border-rose-200',
  },
  SUGGESTION: {
    label: '제안',
    dot: 'bg-amber-500',
    chip: 'bg-amber-100 text-amber-700',
    mark: 'bg-amber-200/70 decoration-amber-400',
    markActive: 'bg-amber-300 ring-2 ring-amber-400',
    cardRing: 'ring-amber-300 border-amber-200',
  },
  INFO: {
    label: '참고',
    dot: 'bg-sky-500',
    chip: 'bg-sky-100 text-sky-700',
    mark: 'bg-sky-200/70 decoration-sky-400',
    markActive: 'bg-sky-300 ring-2 ring-sky-400',
    cardRing: 'ring-sky-300 border-sky-200',
  },
};

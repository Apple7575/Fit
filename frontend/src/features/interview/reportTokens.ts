/**
 * 리포트 화면 타이포 스케일.
 *
 * 리포트가 지저분해 보이는 가장 큰 이유가 글자 크기였다(한 화면에 11·12·13·13.5·14·15·17px 이 섞여 있었다).
 * 여기 있는 조합만 쓴다: 크기는 12 · 14 · 17 · 20 · 28px, 굵기는 400 · 600 · 800 세 가지.
 */
export const T = {
  /** 화면에서 가장 먼저 읽히는 한 문장 (화면당 1개) */
  hero: 'text-[20px] font-extrabold leading-8 text-slate-950 break-keep',
  /** 큰 수치 */
  stat: 'text-[28px] font-extrabold leading-none tabular-nums',
  /** 섹션 제목 */
  section: 'text-[17px] font-extrabold leading-7 text-slate-900 break-keep',
  /** 본문 */
  body: 'text-[14px] font-normal leading-6 text-slate-600 break-keep',
  /** 강조 본문 */
  bodyStrong: 'text-[14px] font-semibold leading-6 text-slate-900 break-keep',
  /** 값·항목 이름 */
  label: 'text-[12px] font-semibold text-slate-500',
  /** 보조 설명 */
  caption: 'text-[12px] font-normal leading-5 text-slate-400',
} as const;

/** 상태 색. 좋음 · 확인 필요 · 측정 없음 세 가지만 쓴다. */
export const TONE = {
  good: { text: 'text-emerald-700', dot: 'bg-emerald-500', bar: 'bg-emerald-500', soft: 'bg-emerald-50' },
  warn: { text: 'text-amber-700', dot: 'bg-amber-500', bar: 'bg-amber-500', soft: 'bg-amber-50' },
  none: { text: 'text-slate-400', dot: 'bg-slate-300', bar: 'bg-slate-300', soft: 'bg-slate-50' },
} as const;

export type ToneKey = keyof typeof TONE;

/** 카드 공통 틀 */
export const CARD = 'rounded-2xl border border-slate-200 bg-white shadow-sm';

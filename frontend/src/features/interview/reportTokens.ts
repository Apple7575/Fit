/**
 * 리포트 화면 타이포 스케일.
 *
 * 리포트가 지저분해 보이는 가장 큰 이유가 글자 크기였다(한 화면에 11·12·13·13.5·14·15·17px 이 섞여 있었다).
 * 여기 있는 조합만 쓴다: 크기는 12 · 14 · 17 · 20 · 28px, 굵기는 400 · 600 · 800 세 가지.
 */
/*
 * 글줄 규칙. 한글은 낱말 단위로 끊고(break-keep), 그래도 한 줄에 못 들어가는 덩어리는
 * 아무 데서나 끊는다(wrap-anywhere).
 *
 * <p>질문·회사명·답변은 사용자나 AI 가 만든 글이라 띄어쓰기가 하나도 없을 수 있다.
 * break-keep 만 붙이면 그런 글이 줄을 못 바꿔 카드를 가로로 뚫고 나간다.
 */
const WRAP = 'break-keep wrap-anywhere';

export const T = {
  /** 화면에서 가장 먼저 읽히는 한 문장 (화면당 1개) */
  hero: `text-[20px] font-extrabold leading-8 text-slate-950 ${WRAP}`,
  /** 큰 수치 */
  stat: 'text-[28px] font-extrabold leading-none tabular-nums',
  /** 섹션 제목 */
  section: `text-[17px] font-extrabold leading-7 text-slate-900 ${WRAP}`,
  /** 본문 */
  body: `text-[14px] font-normal leading-6 text-slate-600 ${WRAP}`,
  /** 강조 본문 */
  bodyStrong: `text-[14px] font-semibold leading-6 text-slate-900 ${WRAP}`,
  /** 값·항목 이름 */
  label: 'text-[12px] font-semibold text-slate-500',
  /** 보조 설명 */
  caption: 'text-[12px] font-normal leading-5 text-slate-400',
} as const;

/**
 * 상태 색. 좋음 · 고칠 것 · 측정 없음 세 가지만 쓴다.
 * 고칠 것은 빨강으로 두되 배경은 아주 연하게 깔아, 화면이 경고문처럼 보이지 않게 한다.
 */
export const TONE = {
  good: {
    text: 'text-emerald-700',
    dot: 'bg-emerald-500',
    bar: 'bg-emerald-500',
    soft: 'bg-emerald-50/70',
    chip: 'bg-emerald-50/70 text-emerald-700 ring-emerald-200',
  },
  warn: {
    text: 'text-red-600',
    dot: 'bg-red-500',
    bar: 'bg-red-400',
    soft: 'bg-red-50/60',
    chip: 'bg-red-50/60 text-red-600 ring-red-200',
  },
  none: {
    text: 'text-slate-400',
    dot: 'bg-slate-300',
    bar: 'bg-slate-300',
    soft: 'bg-slate-50',
    chip: 'bg-slate-50 text-slate-500 ring-slate-200',
  },
} as const;

export type ToneKey = keyof typeof TONE;

/** 카드 공통 틀 */
export const CARD = 'rounded-2xl border border-slate-200 bg-white shadow-sm';

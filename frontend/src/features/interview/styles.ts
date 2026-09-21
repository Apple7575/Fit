import type { InterviewType, PointKind, QuestionSource } from './types';

export const TYPE_LABEL: Record<InterviewType, string> = {
  technical: '기술 면접',
  behavioral: '인성 면접',
};

export const TYPE_OPTIONS: { value: InterviewType; label: string; desc: string; icon: string }[] = [
  { value: 'technical', label: '기술 면접', desc: '직무 기술·문제해결·CS 중심', icon: '⚙️' },
  { value: 'behavioral', label: '인성 면접', desc: '지원동기·경험·협업·인성 중심', icon: '🧑‍🤝‍🧑' },
];

export const SOURCE_BADGE: Record<QuestionSource, { label: string; className: string }> = {
  company: { label: '회사 데이터', className: 'bg-sky-50 text-sky-700 ring-sky-200' },
  cover_letter: { label: '자소서 기반', className: 'bg-violet-50 text-violet-700 ring-violet-200' },
  common: { label: '공통 질문', className: 'bg-slate-100 text-slate-600 ring-slate-200' },
  /*
   * 꼬리질문은 잘못된 것이 아니라 "더 물어볼 만해서" 나온 질문이다. 빨간 배지는 경고로 읽혀
   * 다른 세 종류와 뜻이 달라 보였다. 검은 알약이면 눈에는 띄되 나무라는 느낌이 없다.
   */
  followup: { label: '추가 질문', className: 'bg-slate-900 text-white ring-slate-900' },
};

export const KIND_STYLE: Record<PointKind, { label: string; dot: string; chip: string }> = {
  STRENGTH: { label: '강점', dot: 'bg-emerald-500', chip: 'bg-emerald-50 text-emerald-700' },
  IMPROVEMENT: { label: '개선점', dot: 'bg-amber-500', chip: 'bg-amber-50 text-amber-700' },
};

/**
 * 면접 유형별 포인트 색. 카드 배경은 흰색 그대로 두고 위쪽 띠·배지·머리글자에만 쓴다.
 * 기술 면접은 파랑, 인성 면접은 보라.
 */
export const TYPE_ACCENT: Record<InterviewType, { strip: string; chip: string; avatar: string }> = {
  technical: {
    strip: 'bg-blue-500',
    chip: 'bg-blue-50 text-blue-700 ring-blue-100',
    avatar: 'bg-blue-50 text-blue-700',
  },
  behavioral: {
    strip: 'bg-violet-500',
    chip: 'bg-violet-50 text-violet-700 ring-violet-100',
    avatar: 'bg-violet-50 text-violet-700',
  },
};

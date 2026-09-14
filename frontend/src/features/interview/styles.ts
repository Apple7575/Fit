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
  followup: { label: '추가 질문', className: 'bg-rose-50 text-rose-700 ring-rose-200' },
};

export const KIND_STYLE: Record<PointKind, { label: string; dot: string; chip: string }> = {
  STRENGTH: { label: '강점', dot: 'bg-emerald-500', chip: 'bg-emerald-50 text-emerald-700' },
  IMPROVEMENT: { label: '개선점', dot: 'bg-amber-500', chip: 'bg-amber-50 text-amber-700' },
};

interface SourceBadgeProps {
  /** ai: 모델이 생성한 해석 / data: 공시·수집 데이터 그대로 */
  kind: 'ai' | 'data';
  /** 출처 설명 (예: "DART 주요사항보고서"). 생략하면 종류만 표시 */
  source?: string;
}

/**
 * 화면의 정보가 AI 분석 결과인지 실제 데이터인지 구분하는 배지.
 * 색만이 아니라 문구로 구분한다 (Jira 79 Done: AI 분석과 실제 데이터 구분).
 */
export function SourceBadge({ kind, source }: SourceBadgeProps) {
  const isAi = kind === 'ai';
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold ${
        isAi
          ? 'border border-violet-200 bg-violet-50 text-violet-700'
          : 'border border-slate-200 bg-slate-50 text-slate-600'
      }`}
    >
      <span aria-hidden="true">{isAi ? '✦' : '▣'}</span>
      {isAi ? 'AI 분석' : '실제 데이터'}
      {source && <span className="font-medium opacity-80">· {source}</span>}
    </span>
  );
}

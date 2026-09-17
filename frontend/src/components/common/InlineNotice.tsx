import type { ReactNode } from 'react';

interface InlineNoticeProps {
  children: ReactNode;
  /** 다시 시도 버튼을 보여줄 때 전달 */
  onRetry?: () => void;
}

/** 섹션 안에서 오류·안내를 보여주는 공용 상자. role=alert 로 스크린리더에 즉시 읽힌다. */
export function InlineNotice({ children, onRetry }: InlineNoticeProps) {
  return (
    <p
      className="flex flex-wrap items-center gap-y-2 rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm font-medium text-amber-900"
      role="alert"
    >
      {children}
      {onRetry && (
        <button
          className="ml-3 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-100"
          onClick={onRetry}
          type="button"
        >
          다시 시도
        </button>
      )}
    </p>
  );
}

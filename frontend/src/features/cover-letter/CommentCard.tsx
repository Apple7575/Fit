import { SEVERITY_STYLE } from './severity';
import type { FeedbackComment } from './types';

interface CommentCardProps {
  comment: FeedbackComment;
  commentKey: string;
  active: boolean;
  onHover: (active: boolean) => void;
}

export function CommentCard({ comment, commentKey, active, onHover }: CommentCardProps) {
  const style = SEVERITY_STYLE[comment.severity];

  return (
    <div
      id={`cl-comment-${commentKey}`}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
      className={[
        'scroll-mt-4 rounded-xl border bg-white p-3.5 shadow-sm transition',
        active ? `ring-2 ${style.cardRing}` : 'border-slate-200',
      ].join(' ')}
    >
      <div className="mb-2 flex items-center gap-1.5">
        <span className={`inline-block h-2 w-2 rounded-full ${style.dot}`} />
        <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${style.chip}`}>
          {style.label}
        </span>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
          {comment.category}
        </span>
      </div>

      {comment.quote && (
        <p className="mb-2 border-l-2 border-slate-200 pl-2 text-[13px] text-slate-400 italic">
          “{comment.quote}”
        </p>
      )}

      <p className="text-[13.5px] leading-6 text-slate-700">{comment.message}</p>

      {comment.suggestion && (
        <div className="mt-2 rounded-lg bg-slate-50 p-2.5">
          <p className="mb-0.5 text-[11px] font-semibold text-slate-500">✏️ 개선 제안</p>
          <p className="text-[13.5px] leading-6 text-slate-700">{comment.suggestion}</p>
        </div>
      )}
    </div>
  );
}

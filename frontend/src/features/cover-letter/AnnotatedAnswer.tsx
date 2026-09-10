import { useMemo } from 'react';
import { buildSegments } from './annotate';
import { SEVERITY_STYLE } from './severity';
import type { FeedbackComment } from './types';

interface AnnotatedAnswerProps {
  itemKey: string;
  answer: string;
  comments: FeedbackComment[];
  activeKey: string | null;
  onHover: (key: string | null) => void;
  onSelect: (key: string) => void;
}

/** 답변 본문 + 코멘트 구간 인라인 하이라이트. hover 로 강조, 클릭으로 해당 코멘트로 이동. */
export function AnnotatedAnswer({ itemKey, answer, comments, activeKey, onHover, onSelect }: AnnotatedAnswerProps) {
  const segments = useMemo(() => buildSegments(answer, comments), [answer, comments]);

  return (
    <p className="text-[15px] leading-8 break-keep whitespace-pre-wrap text-slate-700">
      {segments.map((segment, index) => {
        if (segment.commentIndex === undefined) {
          return <span key={index}>{segment.text}</span>;
        }
        const comment = comments[segment.commentIndex];
        const style = SEVERITY_STYLE[comment.severity];
        const key = `${itemKey}#${segment.commentIndex}`;
        const active = activeKey === key;
        return (
          <mark
            key={index}
            onMouseEnter={() => onHover(key)}
            onMouseLeave={() => onHover(null)}
            onClick={() => onSelect(key)}
            className={[
              'cursor-pointer rounded px-0.5 underline decoration-2 underline-offset-4 transition',
              active ? style.markActive : style.mark,
            ].join(' ')}
          >
            {segment.text}
          </mark>
        );
      })}
    </p>
  );
}

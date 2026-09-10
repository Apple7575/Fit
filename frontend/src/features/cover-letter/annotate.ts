import type { FeedbackComment } from './types';

export interface Segment {
  text: string;
  /** 해당 구간에 걸린 코멘트 인덱스. 일반 텍스트면 없다. */
  commentIndex?: number;
}

/**
 * 답변 본문을 코멘트 구간(인용/오프셋)에 따라 분절한다.
 * 서버가 startOffset/endOffset 을 주면 그대로 쓰고, 없으면 quote 를 찾아 위치를 잡는다.
 * 겹치는 구간은 먼저 등장한 것만 남긴다.
 */
export function buildSegments(answer: string, comments: FeedbackComment[]): Segment[] {
  const ranges = comments
    .map((comment, commentIndex) => {
      const hasOffset =
        typeof comment.startOffset === 'number' &&
        typeof comment.endOffset === 'number' &&
        comment.startOffset >= 0 &&
        comment.endOffset <= answer.length &&
        comment.startOffset < comment.endOffset;
      if (hasOffset) {
        return { start: comment.startOffset as number, end: comment.endOffset as number, commentIndex };
      }
      const start = comment.quote ? answer.indexOf(comment.quote) : -1;
      return start === -1 ? null : { start, end: start + comment.quote.length, commentIndex };
    })
    .filter((range): range is NonNullable<typeof range> => range !== null)
    .sort((a, b) => a.start - b.start);

  const clean: typeof ranges = [];
  let lastEnd = -1;
  for (const range of ranges) {
    if (range.start >= lastEnd) {
      clean.push(range);
      lastEnd = range.end;
    }
  }

  const segments: Segment[] = [];
  let cursor = 0;
  for (const range of clean) {
    if (range.start > cursor) segments.push({ text: answer.slice(cursor, range.start) });
    segments.push({ text: answer.slice(range.start, range.end), commentIndex: range.commentIndex });
    cursor = range.end;
  }
  if (cursor < answer.length) segments.push({ text: answer.slice(cursor) });
  return segments;
}

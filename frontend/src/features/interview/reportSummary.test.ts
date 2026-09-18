import { describe, expect, it } from 'vitest';
import type { MetricRow } from './delivery';
import { buildHighlights } from './reportSummary';
import type { FeedbackPoint } from './types';

const point = (
  kind: FeedbackPoint['kind'],
  category: FeedbackPoint['category'],
  message: string,
  suggestion?: string,
): FeedbackPoint => ({ kind, category, message, suggestion: suggestion ?? null });

const row = (key: string, value: string, tone: MetricRow['tone'], hint?: string): MetricRow => ({
  key,
  value,
  tone,
  hint,
});

describe('buildHighlights', () => {
  it('AI 피드백이 있으면 강점·개선점·제안을 순서대로 세 장으로 만든다', () => {
    const highlights = buildHighlights(
      [
        { no: '1', points: [point('STRENGTH', '구체성', '수치로 근거를 들었어요')] },
        { no: '2', points: [point('IMPROVEMENT', '논리성', '결론이 뒤에 나와요', '결론부터 말해 보세요')] },
      ],
      [],
      [],
    );

    expect(highlights.map((h) => h.title)).toEqual(['잘한 것', '고칠 것', '다음에 연습할 것']);
    expect(highlights[0].source).toBe('Q1 · 구체성');
    expect(highlights[2].body).toBe('결론부터 말해 보세요');
  });

  it('AI 피드백이 없으면 로컬 측정에서 좋은 항목과 경고를 가져온다', () => {
    const highlights = buildHighlights(
      [{ no: '1', points: [] }],
      [row('말 속도', '300 음절/분', 'good')],
      [row('정면 유지', '55%', 'warn', '고개를 정면으로 향해 보세요')],
    );

    expect(highlights).toHaveLength(2);
    expect(highlights[0]).toMatchObject({ title: '잘한 것', source: '전달·비언어 측정' });
    expect(highlights[1].body).toContain('정면 유지');
  });

  it('말할 거리가 없으면 카드를 만들지 않는다', () => {
    expect(buildHighlights([{ no: '1', points: [] }], [], [])).toEqual([]);
  });
});

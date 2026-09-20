import { describe, expect, it } from 'vitest';
import type { MetricRow } from './delivery';
import { buildAxes, buildHighlights } from './reportSummary';
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
    // 지표 이름을 조사와 함께 기계적으로 붙이지 않고, 사람이 읽는 개선 문장을 그대로 쓴다
    expect(highlights[1].body).toBe('고개를 정면으로 향해 보세요');
  });

  it('말할 거리가 없으면 카드를 만들지 않는다', () => {
    expect(buildHighlights([{ no: '1', points: [] }], [], [])).toEqual([]);
  });
});

describe('buildAxes', () => {
  it('세 축을 언제나 같은 순서로 만든다', () => {
    expect(buildAxes([], [], null).map((a) => a.key)).toEqual(['content', 'delivery', 'manner']);
  });

  it('측정값이 없으면 점수를 지어내지 않고 측정 없음으로 둔다', () => {
    const axes = buildAxes([{ no: '1', points: [] }], [], null);
    expect(axes.map((a) => a.tone)).toEqual(['none', 'none', 'none']);
    expect(axes[2].status).toBe('측정 없음');
  });

  it('고칠 점이 있으면 개수를, 없으면 좋아요를 보여준다', () => {
    const withFix = buildAxes(
      [{ no: '1', points: [point('IMPROVEMENT', '논리성', '결론이 뒤에 나와요')] }],
      [row('말 속도', '300', 'good'), row('답변 길이', '12초', 'warn', '조금 더 구체적으로')],
      { ok: 6, total: 8 },
    );
    expect(withFix[0]).toMatchObject({ status: '고칠 점 1개', tone: 'warn' });
    expect(withFix[1]).toMatchObject({ status: '1개 확인', detail: '답변 길이', tone: 'warn' });
    expect(withFix[2]).toMatchObject({ status: '2개 확인', tone: 'warn' });

    const allGood = buildAxes(
      [{ no: '1', points: [point('STRENGTH', '구체성', '수치로 근거를 들었어요')] }],
      [row('말 속도', '300', 'good')],
      { ok: 8, total: 8 },
    );
    expect(allGood.map((a) => a.tone)).toEqual(['good', 'good', 'good']);
    expect(allGood[0].detail).toBe('강점 1개');
  });

  it('재지 못한 항목은 적정으로 세지 않는다', () => {
    const axes = buildAxes(
      [{ no: '1', points: [] }],
      [row('말 속도', '재지 못함', 'none'), row('답변 길이', '40초', 'good')],
      null,
    );
    // 못 잰 항목이 고리에 들어가면 없는 측정이 점수가 된다
    expect(axes[1]).toMatchObject({ ok: 1, total: 1, tone: 'good' });
  });

  it('하나도 못 쟀으면 부르는 쪽이 준 까닭을 그대로 쓴다', () => {
    const axes = buildAxes([{ no: '1', points: [] }], [row('말 속도', '재지 못함', 'none')], null, {
      delivery: '녹화한 브라우저에서만 볼 수 있어요',
      manner: '녹화한 브라우저에서만 볼 수 있어요',
    });
    expect(axes[1]).toMatchObject({ status: '측정 없음', detail: '녹화한 브라우저에서만 볼 수 있어요' });
    expect(axes[2].detail).toBe('녹화한 브라우저에서만 볼 수 있어요');
  });
});

import type { MetricRow } from './delivery';
import type { FeedbackPoint } from './types';

export interface Highlight {
  /** 카드 제목 */
  title: string;
  /** 한 문장 */
  body: string;
  /** 어디서 나온 이야기인지 (예: "Q2 · 구체성", "전달력 측정") */
  source: string;
  tone: 'good' | 'fix' | 'next';
}

interface ItemLike {
  no: string;
  points: FeedbackPoint[];
}

/**
 * 리포트 첫 화면의 세 장: 잘한 것 · 고칠 것 · 다음에 연습할 것.
 * AI 피드백(강점·개선점)을 먼저 쓰고, 없으면 로컬 측정(전달·비언어)의 좋은 항목·경고를 쓴다.
 * 없는 카드는 만들지 않는다 (빈 카드로 자리를 채우지 않는다).
 */
export function buildHighlights(
  items: ItemLike[],
  deliveryRows: MetricRow[],
  nonverbalRows: MetricRow[],
): Highlight[] {
  const out: Highlight[] = [];
  const flat = items.flatMap((item) => item.points.map((point) => ({ no: item.no, point })));
  const strength = flat.find((p) => p.point.kind === 'STRENGTH');
  const improvement = flat.find((p) => p.point.kind === 'IMPROVEMENT');
  const withSuggestion = flat.find((p) => p.point.kind === 'IMPROVEMENT' && p.point.suggestion);
  const metricRows = [...deliveryRows, ...nonverbalRows];
  const goodMetric = metricRows.find((r) => r.tone === 'good');
  const warnMetric = metricRows.find((r) => r.tone === 'warn' && r.hint);

  if (strength) {
    out.push({
      title: '잘한 것',
      body: strength.point.message,
      source: `Q${strength.no} · ${strength.point.category}`,
      tone: 'good',
    });
  } else if (goodMetric) {
    out.push({
      title: '잘한 것',
      body: `${goodMetric.key}이(가) 적정 범위였어요. (${goodMetric.value})`,
      source: '전달·비언어 측정',
      tone: 'good',
    });
  }

  if (improvement) {
    out.push({
      title: '고칠 것',
      body: improvement.point.message,
      source: `Q${improvement.no} · ${improvement.point.category}`,
      tone: 'fix',
    });
  } else if (warnMetric) {
    out.push({
      title: '고칠 것',
      body: `${warnMetric.key}을(를) 살펴보세요. (${warnMetric.value})`,
      source: '전달·비언어 측정',
      tone: 'fix',
    });
  }

  // 연습할 것은 "다음에 무엇을 해볼지"라서 개선점의 제안 문장을 우선 쓴다
  if (withSuggestion?.point.suggestion) {
    out.push({
      title: '다음에 연습할 것',
      body: withSuggestion.point.suggestion,
      source: `Q${withSuggestion.no} · ${withSuggestion.point.category}`,
      tone: 'next',
    });
  } else if (warnMetric?.hint && improvement) {
    out.push({ title: '다음에 연습할 것', body: warnMetric.hint, source: '전달·비언어 측정', tone: 'next' });
  }

  return out;
}

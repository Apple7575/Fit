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

/** 리포트 첫 화면의 세 축. 각 축은 상태 한 단어와 한 줄 설명만 보여주고 자세한 값은 접어 둔다. */
export interface Axis {
  key: 'content' | 'delivery' | 'manner';
  title: string;
  /** 상태 한 단어 (예: "좋아요", "2개 확인") */
  status: string;
  /** 상태 아래 한 줄 */
  detail: string;
  tone: 'good' | 'warn' | 'none';
  /** 적정으로 나온 항목 수 / 전체 항목 수. 고리 그래프로 보여준다 (측정이 없으면 total 0) */
  ok: number;
  total: number;
}

/**
 * 답변 내용 · 말하기 · 태도 세 축의 상태를 만든다.
 * 측정값이 없으면 점수를 지어내지 않고 'none'(측정 없음)으로 둔다.
 */
export function buildAxes(
  items: ItemLike[],
  deliveryRows: MetricRow[],
  manner: { ok: number; total: number } | null,
  /**
   * 측정값이 없을 때 그 까닭. 기본값은 "이번에 장비가 꺼져 있었다"는 뜻이다.
   *
   * <p>영상과 자세 분석은 서버에 올라가지 않고 녹화한 브라우저에만 남는다. 그래서 다른 기기나
   * 다른 브라우저에서 저장본을 열면 값이 통째로 비는데, 그때 "카메라를 켜면 봐 드려요"라고 하면
   * 사용자는 카메라를 켰었으므로 고장으로 읽는다. 부르는 쪽이 까닭을 넘겨 준다.
   */
  unmeasured: { delivery: string; manner: string } = {
    delivery: '마이크가 꺼져 있었어요',
    manner: '카메라를 켜면 봐 드려요',
  },
): Axis[] {
  const points = items.flatMap((item) => item.points);
  const strengths = points.filter((p) => p.kind === 'STRENGTH').length;
  const improvements = points.filter((p) => p.kind === 'IMPROVEMENT').length;

  const content: Axis =
    points.length === 0
      ? { key: 'content', title: '답변 내용', status: '분석 없음', detail: '총평만 있습니다', tone: 'none', ok: 0, total: 0 }
      : improvements === 0
        ? {
            key: 'content',
            title: '답변 내용',
            status: '좋아요',
            detail: `강점 ${strengths}개`,
            tone: 'good',
            ok: strengths,
            total: points.length,
          }
        : {
            key: 'content',
            title: '답변 내용',
            status: `고칠 점 ${improvements}개`,
            detail: strengths > 0 ? `강점 ${strengths}개도 있어요` : '강점으로 꼽힌 답변은 없어요',
            tone: 'warn',
            ok: strengths,
            total: points.length,
          };

  // 재지 못한 항목은 고리에서 빼 둔다. 적정으로 세면 없는 측정이 점수가 된다
  const measuredRows = deliveryRows.filter((r) => r.tone !== 'none');
  const warnRows = measuredRows.filter((r) => r.tone === 'warn');
  const okRows = measuredRows.length - warnRows.length;
  const delivery: Axis =
    measuredRows.length === 0
      ? { key: 'delivery', title: '말하기', status: '측정 없음', detail: unmeasured.delivery, tone: 'none', ok: 0, total: 0 }
      : warnRows.length === 0
        ? {
            key: 'delivery',
            title: '말하기',
            status: '좋아요',
            detail: `${measuredRows.length}개 항목 모두 적정`,
            tone: 'good',
            ok: okRows,
            total: measuredRows.length,
          }
        : {
            key: 'delivery',
            title: '말하기',
            status: `${warnRows.length}개 확인`,
            detail: warnRows.map((r) => r.key).join(' · '),
            tone: 'warn',
            ok: okRows,
            total: measuredRows.length,
          };

  const mannerAxis: Axis =
    manner == null || manner.total === 0
      ? { key: 'manner', title: '태도 · 시선', status: '측정 없음', detail: unmeasured.manner, tone: 'none', ok: 0, total: 0 }
      : manner.ok === manner.total
        ? {
            key: 'manner',
            title: '태도 · 시선',
            status: '좋아요',
            detail: `${manner.total}개 항목 모두 적정`,
            tone: 'good',
            ...manner,
          }
        : {
            key: 'manner',
            title: '태도 · 시선',
            status: `${manner.total - manner.ok}개 확인`,
            detail: `${manner.total}개 중 ${manner.ok}개가 적정`,
            tone: 'warn',
            ...manner,
          };

  return [content, delivery, mannerAxis];
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
      body: `${goodMetric.key} ${goodMetric.value} — 적정 범위였어요`,
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
      body: warnMetric.hint ?? `${warnMetric.key} ${warnMetric.value} — 한 번 확인해 보세요`,
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

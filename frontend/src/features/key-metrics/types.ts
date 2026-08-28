export const METRIC_KEYS = [
  'revenue',
  'operatingProfit',
  'netIncome',
  'totalAssets',
  'totalLiabilities',
  'totalEquity',
] as const;

export type MetricKey = (typeof METRIC_KEYS)[number];

export const METRIC_LABELS: Record<MetricKey, string> = {
  revenue: '매출액',
  operatingProfit: '영업이익',
  netIncome: '당기순이익',
  totalAssets: '자산총계',
  totalLiabilities: '부채총계',
  totalEquity: '자본총계',
};

/** 금액은 원(KRW) 단위. 값이 없으면 null (0과 구분). */
export interface KeyMetric {
  key: MetricKey;
  value: number | null;
}

/** GET /activities 의 type 허용값 (명세: facility·corporate_invest·ma·transfer) */
export const ACTIVITY_TYPES = [
  'facility',
  'corporate_invest',
  'ma',
  'transfer',
] as const;

export type ActivityType = (typeof ACTIVITY_TYPES)[number];

export const ACTIVITY_TYPE_LABELS: Record<ActivityType, string> = {
  facility: '설비투자',
  corporate_invest: '타법인 출자',
  ma: 'M&A',
  transfer: '사업 양수도',
};

/** 투자·M&A 이벤트 한 건. 원천은 DART 주요사항보고서. 없는 값은 null. */
export interface InvestmentActivity {
  year: number;
  type: ActivityType;
  /** 투자 분야 (예: 파운드리) */
  field: string | null;
  /** 투자 목적 (예: 미국 테일러 공장 생산능력 확대) */
  purpose: string | null;
  /** 금액(원) */
  amount: number | null;
}

/** GET /segments 의 부문 한 줄. 매출 미공시 부문은 revenue·revenueShare 가 null. */
export interface SegmentChange {
  name: string;
  revenue: number | null;
  revenueShare: number | null;
  /** 부문 직원 순증감(명). 없으면 null */
  employeeChange: number | null;
}

/** GET /segments 의 data. employeeTotalChange 는 전사 순증감이라 부문 합과 다를 수 있다. */
export interface WorkforceChange {
  year: number | null;
  employeeTotalChange: number | null;
  segments: SegmentChange[];
}

/** GET /focus 의 direction — AI 생성물. 화면에서 "AI 분석" 으로 구분 표시한다. */
export interface FocusDirection {
  newBusiness: string[];
  keywords: string[];
  strategyChange: string | null;
}

/** GET /focus 의 rnd — 공시 수치. */
export interface FocusRnd {
  /** R&D 비용(원) */
  expense: number | null;
  /** 전년 대비 증가율(%) */
  growthRate: number | null;
  /** 매출 대비 비중(%) */
  revenueRatio: number | null;
  fields: string[];
}

/** GET /focus 의 data. 둘 다 없으면 조건부 영역 미노출. */
export interface CompanyFocus {
  year: number | null;
  direction: FocusDirection | null;
  rnd: FocusRnd | null;
}

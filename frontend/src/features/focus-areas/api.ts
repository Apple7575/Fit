import { ApiError, apiGet } from '../../api/client';
import {
  mockActivitiesByCompany,
  mockFocusByCompany,
  mockWorkforceByCompany,
} from '../../mocks/focusAreas';
import {
  ACTIVITY_TYPES,
  type ActivityType,
  type CompanyFocus,
  type InvestmentActivity,
  type WorkforceChange,
} from './types';

/** GET /api/companies/{corpCode}/activities?type= 의 data */
export interface ActivitiesResponse {
  items: Array<{
    year: number;
    type: string;
    field?: string | null;
    purpose?: string | null;
    amount?: number | null;
  }>;
}

/** GET /api/companies/{corpCode}/segments 의 data */
export interface SegmentsResponse {
  year?: number | null;
  employeeTotalChange?: number | null;
  segments?: Array<{
    name: string;
    revenue?: number | null;
    revenueShare?: number | null;
    employeeChange?: number | null;
  }>;
}

/** GET /api/companies/{corpCode}/focus 의 data */
export interface FocusResponse {
  year?: number | null;
  direction?: {
    newBusiness?: string[] | null;
    keywords?: string[] | null;
    strategyChange?: string | null;
  } | null;
  rnd?: {
    expense?: number | null;
    growthRate?: number | null;
    revenueRatio?: number | null;
    fields?: string[] | null;
  } | null;
}

const TYPE_SET: ReadonlySet<string> = new Set(ACTIVITY_TYPES);
const isActivityType = (t: string): t is ActivityType => TYPE_SET.has(t);
const num = (v: unknown): number | null => (typeof v === 'number' ? v : null);
const str = (v: unknown): string | null =>
  typeof v === 'string' && v.trim() !== '' ? v : null;
const strList = (v: unknown): string[] =>
  Array.isArray(v) ? v.filter((s): s is string => typeof s === 'string' && s !== '') : [];

/** 모르는 type 은 버리고, 없는 필드는 null 로. 최신 연도가 먼저 오도록 정렬한다. */
export const toActivities = (response: ActivitiesResponse): InvestmentActivity[] =>
  (response.items ?? [])
    .filter((item) => isActivityType(item.type))
    .map((item) => ({
      year: item.year,
      type: item.type as ActivityType,
      field: str(item.field),
      purpose: str(item.purpose),
      amount: num(item.amount),
    }))
    .sort((a, b) => b.year - a.year);

export const toWorkforce = (response: SegmentsResponse): WorkforceChange => ({
  year: num(response.year),
  employeeTotalChange: num(response.employeeTotalChange),
  segments: (response.segments ?? []).map((s) => ({
    name: s.name,
    revenue: num(s.revenue),
    revenueShare: num(s.revenueShare),
    employeeChange: num(s.employeeChange),
  })),
});

/**
 * direction 은 세 값이 전부 비면 null, rnd 는 수치가 전부 null 이고 fields 도 비면 null.
 * 둘 다 null 이면 호출부가 조건부 영역을 통째로 숨긴다.
 */
export const toFocus = (response: FocusResponse): CompanyFocus => {
  const d = response.direction;
  const direction = d
    ? {
        newBusiness: strList(d.newBusiness),
        keywords: strList(d.keywords),
        strategyChange: str(d.strategyChange),
      }
    : null;
  const hasDirection =
    direction !== null &&
    (direction.newBusiness.length > 0 ||
      direction.keywords.length > 0 ||
      direction.strategyChange !== null);

  const r = response.rnd;
  const rnd = r
    ? {
        expense: num(r.expense),
        growthRate: num(r.growthRate),
        revenueRatio: num(r.revenueRatio),
        fields: strList(r.fields),
      }
    : null;
  const hasRnd =
    rnd !== null &&
    (rnd.expense !== null ||
      rnd.growthRate !== null ||
      rnd.revenueRatio !== null ||
      rnd.fields.length > 0);

  return {
    year: num(response.year),
    direction: hasDirection ? direction : null,
    rnd: hasRnd ? rnd : null,
  };
};

/** VITE_API_MOCK 규칙은 key-metrics/api.ts 와 동일 */
const isMockEnabled = () =>
  import.meta.env.VITE_API_MOCK === undefined
    ? import.meta.env.DEV
    : import.meta.env.VITE_API_MOCK === 'true';

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const notFound = () =>
  new ApiError(404, 'COMPANY_NOT_FOUND', '해당 기업을 찾을 수 없습니다.');

export async function fetchActivities(
  corpCode: string,
  type: ActivityType,
  signal?: AbortSignal,
): Promise<InvestmentActivity[]> {
  if (isMockEnabled()) {
    await delay(300);
    const all = mockActivitiesByCompany[corpCode];
    if (!all) throw notFound();
    return toActivities({ items: all.filter((a) => a.type === type) });
  }

  const params = new URLSearchParams({ type });
  const data = await apiGet<ActivitiesResponse>(
    `/api/companies/${encodeURIComponent(corpCode)}/activities?${params}`,
    { signal },
  );
  return toActivities(data);
}

export async function fetchWorkforce(
  corpCode: string,
  signal?: AbortSignal,
): Promise<WorkforceChange> {
  if (isMockEnabled()) {
    await delay(300);
    const data = mockWorkforceByCompany[corpCode];
    if (!data) throw notFound();
    return data;
  }

  const data = await apiGet<SegmentsResponse>(
    `/api/companies/${encodeURIComponent(corpCode)}/segments`,
    { signal },
  );
  return toWorkforce(data);
}

export async function fetchFocus(
  corpCode: string,
  signal?: AbortSignal,
): Promise<CompanyFocus> {
  if (isMockEnabled()) {
    await delay(300);
    const data = mockFocusByCompany[corpCode];
    if (!data) throw notFound();
    return data;
  }

  const data = await apiGet<FocusResponse>(
    `/api/companies/${encodeURIComponent(corpCode)}/focus`,
    { signal },
  );
  return toFocus(data);
}

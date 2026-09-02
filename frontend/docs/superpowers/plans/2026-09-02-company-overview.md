# 기업 개요 화면 (S15P21A504-77) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기업 상세 페이지를 탭 구조로 재편하고 첫 탭인 "기업 개요"(기본정보 카드 + 조건부 사업정보 4섹션)를 구현한다.

**Architecture:** 기존 feature 폴더 패턴(`api.ts` + `use<Name>.ts` + 섹션 컴포넌트 + mock + 테스트)을 따른다. `/companies/:companyId` 를 중첩 라우트로 바꿔 레이아웃(헤더+탭+Outlet)과 탭 페이지를 분리하고, 신규 `features/company-profile/` 이 `GET /api/companies/{corpCode}/profile` 을 담당한다. 기본정보는 기존 `features/company-detail/` 을 v2 계약(address·homepageUrl·dataYear)으로 확장한다.

**Tech Stack:** React 19 + react-router-dom 7 + Tailwind CSS 4 + Vitest/RTL. 신규 라이브러리 추가 금지(도넛 차트는 순수 SVG).

## Global Constraints

- 스펙: `docs/superpowers/specs/2026-09-02-company-overview-design.md`
- 모든 명령은 `frontend/` 디렉터리에서 실행한다 (`npx vitest run <파일>`, `npm run lint`, `npm run build`)
- mock 분기 규칙은 기존과 동일: `VITE_API_MOCK` 미설정 시 DEV 에서만 mock
- 공용 상태는 `useApiQuery`(QueryState: loading/success/error), 오류 표시는 `InlineNotice` 사용
- UI 문구는 한글. 결측 필드 문구는 "정보 없음", 미공시 매출은 "미공시"
- 커밋 메시지: `feat: [S15P21A504-<101|102>] <제목>` (한글 명령형 50자 이내, 101=화면 구성, 102=API 연결·결측 처리)
- 성장 분석·집중 분야·최근 이슈 탭은 비활성 버튼만. 기존 KeyMetrics·FinancialTrend 코드는 삭제하지 않고 화면에서만 제외
- 기존 테스트를 깨뜨리지 않는다. 각 Task 종료 시 해당 테스트 파일이 통과해야 커밋한다

---

### Task 1: CompanyDetail v2 필드 확장 (102)

**Files:**
- Modify: `frontend/src/features/company-detail/api.ts`
- Create: `frontend/src/mocks/companyDetails.ts`
- Test: `frontend/src/features/company-detail/api.test.ts` (신규)

**Interfaces:**
- Consumes: `apiGet`, `ApiError`(`src/api/client.ts`), `mockCompanies`(`src/mocks/companies.ts`)
- Produces: `CompanyDetail` 에 `address: string | null`, `homepageUrl: string | null`, `dataYear: number | null` 추가. `fetchCompanyDetail(corpCode, signal?)` 은 세 필드를 항상 포함(응답에 없으면 null)해 반환한다. Task 3·7 이 이 타입을 소비한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`frontend/src/features/company-detail/api.test.ts`:

```tsx
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchCompanyDetail } from './api';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

describe('fetchCompanyDetail (실 API 경로)', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('v2 필드가 응답에 없으면 null 로 채운다', async () => {
    vi.stubEnv('VITE_API_MOCK', 'false');
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          json({
            success: true,
            data: {
              corpCode: '00126380',
              corpName: '삼성전자',
              stockCode: '005930',
              industryCode: '26',
              industryName: '전기·전자제품 제조업',
              market: 'KOSPI',
              ceo: '한종희',
              establishedDate: '1969-01-13',
            },
          }),
        ),
      ),
    );

    const detail = await fetchCompanyDetail('00126380');

    expect(detail.address).toBeNull();
    expect(detail.homepageUrl).toBeNull();
    expect(detail.dataYear).toBeNull();
  });

  it('v2 필드가 오면 그대로 전달한다', async () => {
    vi.stubEnv('VITE_API_MOCK', 'false');
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          json({
            success: true,
            data: {
              corpCode: '00126380',
              corpName: '삼성전자',
              stockCode: '005930',
              industryCode: '26',
              industryName: '전기·전자제품 제조업',
              market: 'KOSPI',
              ceo: '한종희',
              establishedDate: '1969-01-13',
              address: '경기도 수원시 영통구 삼성로 129',
              homepageUrl: 'https://www.samsung.com',
              dataYear: 2025,
            },
          }),
        ),
      ),
    );

    const detail = await fetchCompanyDetail('00126380');

    expect(detail.address).toBe('경기도 수원시 영통구 삼성로 129');
    expect(detail.homepageUrl).toBe('https://www.samsung.com');
    expect(detail.dataYear).toBe(2025);
  });
});
```

주의: `vi.stubEnv('VITE_API_MOCK', 'false')` 는 모듈 로드 시점 상수 `USE_MOCK` 에는 영향이 없다. 그래서 Step 3 에서 `USE_MOCK` 을 함수 호출 시점 평가로 바꾼다 — 테스트가 이를 강제한다.

- [ ] **Step 2: 테스트 실패 확인**

Run: `npx vitest run src/features/company-detail/api.test.ts`
Expected: FAIL (mock 분기를 타서 address 프로퍼티가 없거나, 실 API 경로여도 address 가 undefined → toBeNull 실패)

- [ ] **Step 3: 구현**

`frontend/src/mocks/companyDetails.ts` (신규):

```tsx
import type { CompanyDetail } from '../features/company-detail/api';

type DetailExtras = Pick<
  CompanyDetail,
  'market' | 'ceo' | 'establishedDate' | 'address' | 'homepageUrl' | 'dataYear'
>;

const EMPTY_EXTRAS: DetailExtras = {
  market: null,
  ceo: null,
  establishedDate: null,
  address: null,
  homepageUrl: null,
  dataYear: null,
};

/**
 * 기본정보 v2 필드(주소·홈페이지·기준연도)의 목업.
 * 삼성전자만 풀 데이터, 현대차는 일부 결측 — 결측 상태 화면 확인용.
 */
export const mockCompanyDetailExtras: Record<string, DetailExtras> = {
  '00126380': {
    market: 'KOSPI',
    ceo: '한종희, 경계현',
    establishedDate: '1969-01-13',
    address: '경기도 수원시 영통구 삼성로 129',
    homepageUrl: 'https://www.samsung.com',
    dataYear: 2025,
  },
  '90000002': {
    market: 'KOSPI',
    ceo: '정의선',
    establishedDate: null,
    address: '서울특별시 서초구 헌릉로 12',
    homepageUrl: null,
    dataYear: 2025,
  },
};

export const detailExtrasFor = (corpCode: string): DetailExtras =>
  mockCompanyDetailExtras[corpCode] ?? EMPTY_EXTRAS;
```

`frontend/src/features/company-detail/api.ts` 수정:

```tsx
import { ApiError, apiGet } from '../../api/client';
import { mockCompanies } from '../../mocks/companies';
import { detailExtrasFor } from '../../mocks/companyDetails';

/**
 * GET /api/companies/{corpCode} 의 data 부분 (v2).
 * address·homepageUrl·dataYear 는 백엔드 v2 배포 전에는 응답에 없을 수 있어
 * fetch 쪽에서 null 로 정규화한다.
 */
export interface CompanyDetail {
  corpCode: string;
  corpName: string;
  stockCode: string | null;
  industryCode: string | null;
  industryName: string | null;
  market: string | null;
  ceo: string | null;
  establishedDate: string | null;
  address: string | null;
  homepageUrl: string | null;
  dataYear: number | null;
}

/** VITE_API_MOCK 규칙은 key-metrics/api.ts 와 동일. 테스트에서 stubEnv 로 바꿀 수 있게 호출 시점에 평가한다. */
const useMock = () =>
  import.meta.env.VITE_API_MOCK === undefined
    ? import.meta.env.DEV
    : import.meta.env.VITE_API_MOCK === 'true';

export async function fetchCompanyDetail(
  corpCode: string,
  signal?: AbortSignal,
): Promise<CompanyDetail> {
  if (useMock()) {
    await new Promise((resolve) => setTimeout(resolve, 300));
    const company = mockCompanies.find((c) => c.corpCode === corpCode);
    if (!company) {
      throw new ApiError(404, 'COMPANY_NOT_FOUND', '해당 기업을 찾을 수 없습니다.');
    }
    return { ...company, ...detailExtrasFor(corpCode) };
  }

  const data = await apiGet<CompanyDetail>(
    `/api/companies/${encodeURIComponent(corpCode)}`,
    { signal },
  );
  // v2 미배포 백엔드 응답 방어: 없는 필드는 null 로 채운다
  return {
    ...data,
    market: data.market ?? null,
    ceo: data.ceo ?? null,
    establishedDate: data.establishedDate ?? null,
    address: data.address ?? null,
    homepageUrl: data.homepageUrl ?? null,
    dataYear: data.dataYear ?? null,
  };
}
```

- [ ] **Step 4: 테스트 통과 확인 + 기존 테스트 회귀 확인**

Run: `npx vitest run src/features/company-detail/api.test.ts src/pages/company-detail/CompanyDetailPage.test.tsx`
Expected: PASS (페이지 테스트는 detail 응답에 새 필드가 없어도 null 정규화로 통과)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/company-detail/api.ts frontend/src/mocks/companyDetails.ts frontend/src/features/company-detail/api.test.ts
git commit -m "feat: [S15P21A504-102] 기업 기본정보 v2 필드 추가"
```

---

### Task 2: company-profile 타입·API·훅 (102)

**Files:**
- Create: `frontend/src/features/company-profile/types.ts`
- Create: `frontend/src/features/company-profile/api.ts`
- Create: `frontend/src/features/company-profile/useCompanyProfile.ts`
- Create: `frontend/src/mocks/companyProfile.ts`
- Test: `frontend/src/features/company-profile/api.test.ts`

**Interfaces:**
- Consumes: `apiGet`, `ApiError`, `useApiQuery`
- Produces:
  - `interface ProfileSegment { code: string; revenue: number | null; revenueShare: number | null }`
  - `interface CompanyProfile { year: number; businesses: string[]; segments: ProfileSegment[]; totalRevenue: number | null; products: string[] }`
  - `fetchCompanyProfile(corpCode: string, signal?: AbortSignal): Promise<CompanyProfile>`
  - `useCompanyProfile(corpCode: string): { state: QueryState<CompanyProfile>; retry: () => void }`
  - Task 5·6 이 이 타입·훅을 소비한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`frontend/src/features/company-profile/api.test.ts`:

```tsx
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import { fetchCompanyProfile } from './api';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

describe('fetchCompanyProfile', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('profile 응답을 그대로 반환하고 없는 필드는 빈 값으로 채운다', async () => {
    vi.stubEnv('VITE_API_MOCK', 'false');
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          json({
            success: true,
            data: {
              year: 2025,
              businesses: ['반도체', '스마트폰', '가전'],
              segments: [
                { code: 'DS', revenue: 232000000000000, revenueShare: 58.0 },
                { code: 'DX', revenue: 168000000000000, revenueShare: 42.0 },
              ],
              totalRevenue: 400000000000000,
              products: ['HBM', 'DRAM'],
            },
          }),
        ),
      ),
    );

    const profile = await fetchCompanyProfile('00126380');

    expect(profile.businesses).toEqual(['반도체', '스마트폰', '가전']);
    expect(profile.segments[0]).toEqual({
      code: 'DS',
      revenue: 232000000000000,
      revenueShare: 58.0,
    });
    expect(profile.totalRevenue).toBe(400000000000000);
  });

  it('배열 필드가 응답에 없으면 빈 배열로 정규화한다', async () => {
    vi.stubEnv('VITE_API_MOCK', 'false');
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(json({ success: true, data: { year: 2025 } })),
      ),
    );

    const profile = await fetchCompanyProfile('00126380');

    expect(profile.businesses).toEqual([]);
    expect(profile.segments).toEqual([]);
    expect(profile.products).toEqual([]);
    expect(profile.totalRevenue).toBeNull();
  });

  it('404 는 ApiError(COMPANY_NOT_FOUND) 로 던진다', async () => {
    vi.stubEnv('VITE_API_MOCK', 'false');
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          json(
            {
              success: false,
              error: { code: 'COMPANY_NOT_FOUND', message: '없음' },
            },
            404,
          ),
        ),
      ),
    );

    await expect(fetchCompanyProfile('99999999')).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      code: 'COMPANY_NOT_FOUND',
    } satisfies Partial<ApiError>);
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `npx vitest run src/features/company-profile/api.test.ts`
Expected: FAIL ("Failed to resolve import ./api")

- [ ] **Step 3: 구현**

`frontend/src/features/company-profile/types.ts`:

```tsx
/** GET /api/companies/{corpCode}/profile 의 data.segments[] 항목 */
export interface ProfileSegment {
  code: string;
  /** 매출 미공시 부문은 null */
  revenue: number | null;
  revenueShare: number | null;
}

/** GET /api/companies/{corpCode}/profile 의 data 부분 */
export interface CompanyProfile {
  year: number;
  businesses: string[];
  segments: ProfileSegment[];
  totalRevenue: number | null;
  products: string[];
}
```

`frontend/src/mocks/companyProfile.ts`:

```tsx
import type { CompanyProfile } from '../features/company-profile/types';

/**
 * 백엔드 /profile 미구현 동안 화면 확인용 목업.
 * 삼성전자 풀 데이터 / 현대차 일부만 / NAVER 전부 없음(조건부 섹션 전체 미노출 확인용).
 */
export const mockCompanyProfiles: Record<string, CompanyProfile> = {
  '00126380': {
    year: 2025,
    businesses: ['반도체', '스마트폰', '가전'],
    segments: [
      { code: 'DS', revenue: 232000000000000, revenueShare: 58.0 },
      { code: 'DX', revenue: 168000000000000, revenueShare: 42.0 },
      { code: 'SDC', revenue: null, revenueShare: null },
    ],
    totalRevenue: 400000000000000,
    products: ['HBM', 'DRAM', 'NAND', '스마트폰', 'TV', '모니터'],
  },
  '90000002': {
    year: 2025,
    businesses: ['완성차', '모빌리티 서비스'],
    segments: [],
    totalRevenue: null,
    products: [],
  },
  '90000004': {
    year: 2025,
    businesses: [],
    segments: [],
    totalRevenue: null,
    products: [],
  },
};
```

`frontend/src/features/company-profile/api.ts`:

```tsx
import { ApiError, apiGet } from '../../api/client';
import { mockCompanyProfiles } from '../../mocks/companyProfile';
import type { CompanyProfile } from './types';

/** VITE_API_MOCK 규칙은 company-detail/api.ts 와 동일 */
const useMock = () =>
  import.meta.env.VITE_API_MOCK === undefined
    ? import.meta.env.DEV
    : import.meta.env.VITE_API_MOCK === 'true';

export async function fetchCompanyProfile(
  corpCode: string,
  signal?: AbortSignal,
): Promise<CompanyProfile> {
  if (useMock()) {
    await new Promise((resolve) => setTimeout(resolve, 300));
    const profile = mockCompanyProfiles[corpCode];
    if (!profile) {
      throw new ApiError(404, 'COMPANY_NOT_FOUND', '해당 기업을 찾을 수 없습니다.');
    }
    return profile;
  }

  const data = await apiGet<Partial<CompanyProfile>>(
    `/api/companies/${encodeURIComponent(corpCode)}/profile`,
    { signal },
  );
  // 백엔드 초기 구현이 일부 필드를 생략해도 화면이 깨지지 않게 정규화한다
  return {
    year: data.year ?? 0,
    businesses: data.businesses ?? [],
    segments: data.segments ?? [],
    totalRevenue: data.totalRevenue ?? null,
    products: data.products ?? [],
  };
}
```

`frontend/src/features/company-profile/useCompanyProfile.ts`:

```tsx
import { useCallback } from 'react';
import { useApiQuery, type QueryState } from '../../hooks/useApiQuery';
import { fetchCompanyProfile } from './api';
import type { CompanyProfile } from './types';

export type CompanyProfileState = QueryState<CompanyProfile>;

/** corpCode 가 바뀌면 기업 프로필을 다시 조회한다. 진행 중 요청은 취소. */
export function useCompanyProfile(corpCode: string) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchCompanyProfile(corpCode, signal),
    [corpCode],
  );
  return useApiQuery(`company-profile|${corpCode}`, fetcher);
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `npx vitest run src/features/company-profile/api.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/company-profile frontend/src/mocks/companyProfile.ts
git commit -m "feat: [S15P21A504-102] 기업 프로필 API 연동 기반 추가"
```

---

### Task 3: 기업 기본정보 카드 (101)

**Files:**
- Create: `frontend/src/features/company-profile/CompanyBasicInfoCard.tsx`
- Test: `frontend/src/features/company-profile/CompanyBasicInfoCard.test.tsx`

**Interfaces:**
- Consumes: `CompanyDetail`, `CompanyDetailState`(Task 1, `features/company-detail`)
- Produces: `CompanyBasicInfoCard({ corpCode, state }: { corpCode: string; state: CompanyDetailState })`. Task 7 의 Overview 탭이 소비한다.
  - 로딩: 스켈레톤. 오류: F-31 규칙 — 제목 "기업 분석" + 전 필드 "정보 없음" 으로 카드 유지
  - 성공: 이니셜 로고 + 기업명 + 업종·대표자·설립일·주소·홈페이지, null 필드는 "정보 없음"
  - 홈페이지는 값이 있을 때만 새 탭 링크

- [ ] **Step 1: 실패하는 테스트 작성**

`frontend/src/features/company-profile/CompanyBasicInfoCard.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ApiError } from '../../api/client';
import type { CompanyDetail } from '../company-detail/api';
import { CompanyBasicInfoCard } from './CompanyBasicInfoCard';

const fullDetail: CompanyDetail = {
  corpCode: '00126380',
  corpName: '삼성전자',
  stockCode: '005930',
  industryCode: '26',
  industryName: '전기·전자제품 제조업',
  market: 'KOSPI',
  ceo: '한종희, 경계현',
  establishedDate: '1969-01-13',
  address: '경기도 수원시 영통구 삼성로 129',
  homepageUrl: 'https://www.samsung.com',
  dataYear: 2025,
};

describe('CompanyBasicInfoCard', () => {
  it('성공 시 기본정보 필드를 모두 보여준다', () => {
    render(
      <CompanyBasicInfoCard
        corpCode="00126380"
        state={{ status: 'success', data: fullDetail }}
      />,
    );

    expect(
      screen.getByRole('heading', { level: 1, name: '삼성전자' }),
    ).toBeInTheDocument();
    expect(screen.getByText('전기·전자제품 제조업')).toBeInTheDocument();
    expect(screen.getByText('한종희, 경계현')).toBeInTheDocument();
    expect(screen.getByText('1969년 1월 13일')).toBeInTheDocument();
    expect(
      screen.getByText('경기도 수원시 영통구 삼성로 129'),
    ).toBeInTheDocument();

    const homepage = screen.getByRole('link', { name: /samsung\.com/ });
    expect(homepage).toHaveAttribute('href', 'https://www.samsung.com');
    expect(homepage).toHaveAttribute('target', '_blank');
  });

  it('null 필드는 "정보 없음" 으로 표시하고 홈페이지 링크는 만들지 않는다', () => {
    render(
      <CompanyBasicInfoCard
        corpCode="00126380"
        state={{
          status: 'success',
          data: {
            ...fullDetail,
            ceo: null,
            establishedDate: null,
            address: null,
            homepageUrl: null,
          },
        }}
      />,
    );

    expect(screen.getAllByText('정보 없음')).toHaveLength(4);
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  it('오류여도 카드는 유지된다 (F-31)', () => {
    render(
      <CompanyBasicInfoCard
        corpCode="00126380"
        state={{
          status: 'error',
          error: new ApiError(500, 'INTERNAL_ERROR', '서버 오류'),
        }}
      />,
    );

    expect(
      screen.getByRole('heading', { level: 1, name: '기업 분석' }),
    ).toBeInTheDocument();
    expect(screen.getAllByText('정보 없음').length).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `npx vitest run src/features/company-profile/CompanyBasicInfoCard.test.tsx`
Expected: FAIL ("Failed to resolve import ./CompanyBasicInfoCard")

- [ ] **Step 3: 구현**

`frontend/src/features/company-profile/CompanyBasicInfoCard.tsx`:

```tsx
import type { ReactNode } from 'react';
import type { CompanyDetailState } from '../company-detail/useCompanyDetail';

interface CompanyBasicInfoCardProps {
  corpCode: string;
  state: CompanyDetailState;
}

const MISSING = '정보 없음';

/** "1969-01-13" → "1969년 1월 13일". 형식이 다르면 원문 그대로 보여준다. */
function formatDate(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) {
    return value;
  }
  return `${match[1]}년 ${Number(match[2])}월 ${Number(match[3])}일`;
}

/** 기업명·업종·대표자·설립일·주소·홈페이지 카드. 오류여도 카드 골격은 유지한다 (F-31). */
export function CompanyBasicInfoCard({
  corpCode,
  state,
}: CompanyBasicInfoCardProps) {
  if (state.status === 'loading') {
    return (
      <section
        aria-busy="true"
        className="animate-pulse rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
        role="status"
      >
        <span className="sr-only">기업 기본정보를 불러오는 중입니다</span>
        <div className="flex gap-6">
          <div className="hidden size-28 rounded-2xl bg-slate-100 sm:block" />
          <div className="flex-1 space-y-4">
            <div className="h-8 w-1/3 rounded-full bg-slate-200" />
            <div className="h-4 w-2/3 rounded-full bg-slate-100" />
            <div className="h-4 w-1/2 rounded-full bg-slate-100" />
          </div>
        </div>
      </section>
    );
  }

  const detail = state.status === 'success' ? state.data : null;
  const corpName = detail?.corpName ?? '기업 분석';
  const initial = detail?.corpName?.charAt(0) ?? '?';

  return (
    <section
      aria-labelledby="company-basic-info-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <div className="flex flex-col gap-6 sm:flex-row sm:gap-8">
        <div
          aria-hidden="true"
          className="hidden size-28 shrink-0 items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 text-4xl font-extrabold text-blue-600 sm:flex"
        >
          {initial}
        </div>

        <div className="min-w-0 flex-1">
          <h1
            className="text-3xl font-extrabold tracking-tight text-slate-950 sm:text-4xl"
            id="company-basic-info-title"
          >
            {corpName}
          </h1>
          <p className="mt-2 text-sm text-slate-500">기업코드 {corpCode}</p>

          <dl className="mt-6 grid grid-cols-1 gap-x-8 gap-y-5 border-t border-slate-100 pt-6 sm:grid-cols-2 lg:grid-cols-3">
            <InfoItem label="업종">{detail?.industryName}</InfoItem>
            <InfoItem label="대표자">{detail?.ceo}</InfoItem>
            <InfoItem label="설립일">
              {detail?.establishedDate
                ? formatDate(detail.establishedDate)
                : null}
            </InfoItem>
            <InfoItem label="본사 위치">{detail?.address}</InfoItem>
            <InfoItem label="홈페이지">
              {detail?.homepageUrl ? (
                <a
                  className="font-semibold text-blue-600 underline-offset-2 hover:underline"
                  href={detail.homepageUrl}
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  {detail.homepageUrl.replace(/^https?:\/\//, '')}
                </a>
              ) : null}
            </InfoItem>
          </dl>
        </div>
      </div>
    </section>
  );
}

function InfoItem({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div>
      <dt className="text-xs font-bold text-slate-400">{label}</dt>
      <dd className="mt-1 text-sm font-medium text-slate-900">
        {children ?? <span className="text-slate-400">{MISSING}</span>}
      </dd>
    </div>
  );
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `npx vitest run src/features/company-profile/CompanyBasicInfoCard.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/company-profile/CompanyBasicInfoCard.tsx frontend/src/features/company-profile/CompanyBasicInfoCard.test.tsx
git commit -m "feat: [S15P21A504-101] 기업 기본정보 카드 구현"
```

---

### Task 4: 주요 사업·주요 제품 카드 (101)

**Files:**
- Create: `frontend/src/features/company-profile/BusinessCard.tsx`
- Create: `frontend/src/features/company-profile/ProductCard.tsx`
- Test: `frontend/src/features/company-profile/BusinessProductCards.test.tsx`

**Interfaces:**
- Consumes: 없음 (순수 프레젠테이션)
- Produces: `BusinessCard({ items }: { items: string[] })`, `ProductCard({ items }: { items: string[] })`. 빈 배열 판단은 호출부(Task 6)가 하므로 여기서는 렌더만 한다. Task 6 이 소비한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`frontend/src/features/company-profile/BusinessProductCards.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { BusinessCard } from './BusinessCard';
import { ProductCard } from './ProductCard';

describe('BusinessCard', () => {
  it('주요 사업명을 모두 보여준다', () => {
    render(<BusinessCard items={['반도체', '스마트폰', '가전']} />);

    expect(
      screen.getByRole('heading', { name: '주요 사업' }),
    ).toBeInTheDocument();
    expect(screen.getByText('반도체')).toBeInTheDocument();
    expect(screen.getByText('스마트폰')).toBeInTheDocument();
    expect(screen.getByText('가전')).toBeInTheDocument();
  });
});

describe('ProductCard', () => {
  it('주요 제품명을 모두 보여준다', () => {
    render(<ProductCard items={['HBM', 'DRAM', 'NAND']} />);

    expect(
      screen.getByRole('heading', { name: '주요 제품' }),
    ).toBeInTheDocument();
    expect(screen.getByText('HBM')).toBeInTheDocument();
    expect(screen.getByText('DRAM')).toBeInTheDocument();
    expect(screen.getByText('NAND')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `npx vitest run src/features/company-profile/BusinessProductCards.test.tsx`
Expected: FAIL (import 실패)

- [ ] **Step 3: 구현**

`frontend/src/features/company-profile/BusinessCard.tsx`:

```tsx
interface BusinessCardProps {
  items: string[];
}

/** 주요 사업. API 가 이름 문자열만 주므로 이름 카드 그리드로 표시한다. */
export function BusinessCard({ items }: BusinessCardProps) {
  return (
    <section
      aria-labelledby="business-card-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <h2
        className="text-xl font-extrabold text-slate-950"
        id="business-card-title"
      >
        주요 사업
      </h2>
      <ul className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
        {items.map((name) => (
          <li
            className="flex min-h-20 items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 px-3 py-4 text-center text-sm font-bold text-slate-900"
            key={name}
          >
            {name}
          </li>
        ))}
      </ul>
    </section>
  );
}
```

`frontend/src/features/company-profile/ProductCard.tsx`:

```tsx
interface ProductCardProps {
  items: string[];
}

/** 주요 제품. 이름 배지 나열. */
export function ProductCard({ items }: ProductCardProps) {
  return (
    <section
      aria-labelledby="product-card-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <h2
        className="text-xl font-extrabold text-slate-950"
        id="product-card-title"
      >
        주요 제품
      </h2>
      <ul className="mt-5 flex flex-wrap gap-2.5">
        {items.map((name) => (
          <li
            className="rounded-full border border-blue-100 bg-blue-50 px-4 py-2 text-sm font-bold text-blue-700"
            key={name}
          >
            {name}
          </li>
        ))}
      </ul>
      <p className="mt-4 text-xs text-slate-400">
        * 주요 제품은 대표 제품 기준으로 선정되었습니다.
      </p>
    </section>
  );
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `npx vitest run src/features/company-profile/BusinessProductCards.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/company-profile/BusinessCard.tsx frontend/src/features/company-profile/ProductCard.tsx frontend/src/features/company-profile/BusinessProductCards.test.tsx
git commit -m "feat: [S15P21A504-101] 주요 사업·주요 제품 카드 구현"
```

---

### Task 5: 사업부 카드 + 사업부 매출 도넛 카드 (101)

**Files:**
- Create: `frontend/src/features/company-profile/SegmentCard.tsx`
- Create: `frontend/src/features/company-profile/SegmentRevenueCard.tsx`
- Test: `frontend/src/features/company-profile/SegmentCards.test.tsx`

**Interfaces:**
- Consumes: `ProfileSegment`(Task 2), `formatAmount`(`src/utils/formatAmount.ts`)
- Produces: `SegmentCard({ segments }: { segments: ProfileSegment[] })`, `SegmentRevenueCard({ segments, totalRevenue }: { segments: ProfileSegment[]; totalRevenue: number | null })`. Task 6 이 소비한다.
  - SegmentRevenueCard 규칙: `revenue === null` 부문은 도넛 호에서 제외하고 범례에 "미공시" 로 표시. 공시 부문이 0개면 카드 렌더 안 함(호출부 방어와 이중)

- [ ] **Step 1: 실패하는 테스트 작성**

`frontend/src/features/company-profile/SegmentCards.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { ProfileSegment } from './types';
import { SegmentCard } from './SegmentCard';
import { SegmentRevenueCard } from './SegmentRevenueCard';

const segments: ProfileSegment[] = [
  { code: 'DS', revenue: 232000000000000, revenueShare: 58.0 },
  { code: 'DX', revenue: 168000000000000, revenueShare: 42.0 },
  { code: 'SDC', revenue: null, revenueShare: null },
];

describe('SegmentCard', () => {
  it('사업부 코드와 매출을 보여주고 미공시 매출은 "미공시" 로 표시한다', () => {
    render(<SegmentCard segments={segments} />);

    expect(screen.getByRole('heading', { name: '사업부' })).toBeInTheDocument();
    expect(screen.getAllByText('DS').length).toBeGreaterThan(0);
    expect(screen.getByText(/232조/)).toBeInTheDocument();
    expect(screen.getByText('미공시')).toBeInTheDocument();
  });
});

describe('SegmentRevenueCard', () => {
  it('공시 부문만 도넛에 그리고 전체 매출을 가운데에 보여준다', () => {
    render(
      <SegmentRevenueCard
        segments={segments}
        totalRevenue={400000000000000}
      />,
    );

    expect(
      screen.getByRole('heading', { name: '사업부 매출' }),
    ).toBeInTheDocument();
    expect(screen.getByText(/400조/)).toBeInTheDocument();
    expect(screen.getByText('58.0%')).toBeInTheDocument();
    expect(screen.getByText('42.0%')).toBeInTheDocument();
    // 미공시 부문은 범례에 "미공시" 로 남는다
    expect(screen.getByText('미공시')).toBeInTheDocument();
    // 도넛 호는 공시 부문 2개만
    expect(
      document.querySelectorAll('[data-testid="donut-arc"]'),
    ).toHaveLength(2);
  });

  it('공시 부문이 하나도 없으면 아무것도 렌더하지 않는다', () => {
    const { container } = render(
      <SegmentRevenueCard
        segments={[{ code: 'A', revenue: null, revenueShare: null }]}
        totalRevenue={null}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `npx vitest run src/features/company-profile/SegmentCards.test.tsx`
Expected: FAIL (import 실패)

- [ ] **Step 3: 구현**

`frontend/src/features/company-profile/SegmentCard.tsx`:

```tsx
import { formatAmount } from '../../utils/formatAmount';
import type { ProfileSegment } from './types';

interface SegmentCardProps {
  segments: ProfileSegment[];
}

/** 사업부 목록. API 가 code·매출만 주므로 코드 아바타 + 매출 행으로 표시한다. */
export function SegmentCard({ segments }: SegmentCardProps) {
  return (
    <section
      aria-labelledby="segment-card-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <h2
        className="text-xl font-extrabold text-slate-950"
        id="segment-card-title"
      >
        사업부
      </h2>
      <ul className="mt-5 space-y-3">
        {segments.map((segment) => (
          <li
            className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3.5"
            key={segment.code}
          >
            <span
              aria-hidden="true"
              className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-sm font-extrabold text-white"
            >
              {segment.code.slice(0, 3)}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-bold text-slate-900">{segment.code}</p>
              <p className="mt-0.5 text-sm text-slate-500">
                {segment.revenue !== null ? (
                  <>
                    매출 {formatAmount(segment.revenue)} 원
                    {segment.revenueShare !== null &&
                      ` · ${segment.revenueShare.toFixed(1)}%`}
                  </>
                ) : (
                  '미공시'
                )}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
```

`frontend/src/features/company-profile/SegmentRevenueCard.tsx`:

```tsx
import { formatAmount } from '../../utils/formatAmount';
import type { ProfileSegment } from './types';

interface SegmentRevenueCardProps {
  segments: ProfileSegment[];
  totalRevenue: number | null;
}

const COLORS = ['#2563eb', '#8b5cf6', '#38bdf8', '#f59e0b', '#10b981', '#f43f5e'];
/** 둘레가 정확히 100 이 되는 반지름 → stroke-dasharray 를 % 처럼 쓴다 */
const RADIUS = 15.915494309189535;

/** 사업부 매출 도넛. 매출 미공시 부문은 호에서 제외하고 범례에 "미공시" 로 남긴다. */
export function SegmentRevenueCard({
  segments,
  totalRevenue,
}: SegmentRevenueCardProps) {
  const disclosed = segments.filter((s) => s.revenue !== null);
  if (disclosed.length === 0) {
    return null;
  }

  const sum = disclosed.reduce((acc, s) => acc + (s.revenue ?? 0), 0);
  let cursor = 25; // 12시 방향에서 시작
  const arcs = disclosed.map((segment, index) => {
    const ratio = sum > 0 ? ((segment.revenue ?? 0) / sum) * 100 : 0;
    const arc = {
      segment,
      ratio,
      offset: cursor,
      color: COLORS[index % COLORS.length],
    };
    cursor -= ratio;
    return arc;
  });
  const undisclosed = segments.filter((s) => s.revenue === null);

  return (
    <section
      aria-labelledby="segment-revenue-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <h2
        className="text-xl font-extrabold text-slate-950"
        id="segment-revenue-title"
      >
        사업부 매출
      </h2>

      <div className="mt-6 flex flex-col items-center gap-8 sm:flex-row">
        <div className="relative size-44 shrink-0">
          <svg aria-hidden="true" className="size-full" viewBox="0 0 42 42">
            {arcs.map(({ segment, ratio, offset, color }) => (
              <circle
                cx="21"
                cy="21"
                data-testid="donut-arc"
                fill="none"
                key={segment.code}
                r={RADIUS}
                stroke={color}
                strokeDasharray={`${ratio} ${100 - ratio}`}
                strokeDashoffset={offset}
                strokeWidth="6"
              />
            ))}
          </svg>
          {totalRevenue !== null && (
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-xs font-medium text-slate-500">
                전체 매출
              </span>
              <span className="text-sm font-extrabold text-slate-950">
                {formatAmount(totalRevenue)} 원
              </span>
            </div>
          )}
        </div>

        <ul className="w-full min-w-0 flex-1 space-y-2.5">
          {arcs.map(({ segment, ratio, color }) => (
            <li
              className="flex items-center gap-3 rounded-xl bg-slate-50 px-4 py-2.5 text-sm"
              key={segment.code}
            >
              <span
                aria-hidden="true"
                className="size-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: color }}
              />
              <span className="min-w-0 flex-1 truncate font-bold text-slate-900">
                {segment.code}
              </span>
              <span className="font-medium text-slate-600">
                {formatAmount(segment.revenue ?? 0)} 원
              </span>
              <span className="w-14 text-right font-semibold text-slate-500">
                {(segment.revenueShare ?? ratio).toFixed(1)}%
              </span>
            </li>
          ))}
          {undisclosed.map((segment) => (
            <li
              className="flex items-center gap-3 rounded-xl bg-slate-50 px-4 py-2.5 text-sm"
              key={segment.code}
            >
              <span
                aria-hidden="true"
                className="size-2.5 shrink-0 rounded-full bg-slate-300"
              />
              <span className="min-w-0 flex-1 truncate font-bold text-slate-900">
                {segment.code}
              </span>
              <span className="font-medium text-slate-400">미공시</span>
            </li>
          ))}
        </ul>
      </div>

      <p className="mt-5 text-xs text-slate-400">* 연결 기준 매출액</p>
    </section>
  );
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `npx vitest run src/features/company-profile/SegmentCards.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/company-profile/SegmentCard.tsx frontend/src/features/company-profile/SegmentRevenueCard.tsx frontend/src/features/company-profile/SegmentCards.test.tsx
git commit -m "feat: [S15P21A504-101] 사업부·사업부 매출 카드 구현"
```

---

### Task 6: CompanyProfileSections 조건부 조립 (102)

**Files:**
- Create: `frontend/src/features/company-profile/CompanyProfileSections.tsx`
- Test: `frontend/src/features/company-profile/CompanyProfileSections.test.tsx`

**Interfaces:**
- Consumes: `useCompanyProfile`(Task 2), `BusinessCard`·`ProductCard`(Task 4), `SegmentCard`·`SegmentRevenueCard`(Task 5), `InlineNotice`
- Produces: `CompanyProfileSections({ corpCode }: { corpCode: string })`. Task 7 의 Overview 탭이 소비한다.
  - 결측 규칙(스펙 그대로): 배열 empty → 해당 카드 미노출 / 404 또는 전 배열 empty → 전체 null / 그 외 오류 → InlineNotice + 다시 시도 / 사업부 매출 카드는 공시 부문 1개 이상일 때만

- [ ] **Step 1: 실패하는 테스트 작성**

`frontend/src/features/company-profile/CompanyProfileSections.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { CompanyProfileSections } from './CompanyProfileSections';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

const stubProfile = (data: unknown, status = 200, code = 'OK') => {
  vi.stubEnv('VITE_API_MOCK', 'false'); // 실 API 경로를 타야 fetch 스텁이 쓰인다
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      Promise.resolve(
        status === 200
          ? json({ success: true, data })
          : json({ success: false, error: { code, message: '오류' } }, status),
      ),
    ),
  );
};

describe('CompanyProfileSections', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('데이터가 있는 섹션만 렌더한다', async () => {
    stubProfile({
      year: 2025,
      businesses: ['반도체'],
      segments: [],
      totalRevenue: null,
      products: [],
    });

    render(<CompanyProfileSections corpCode="00126380" />);

    expect(
      await screen.findByRole('heading', { name: '주요 사업' }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: '사업부' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: '주요 제품' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: '사업부 매출' }),
    ).not.toBeInTheDocument();
  });

  it('전 배열이 비어 있으면 아무것도 렌더하지 않는다', async () => {
    stubProfile({
      year: 2025,
      businesses: [],
      segments: [],
      totalRevenue: null,
      products: [],
    });

    const { container } = render(
      <CompanyProfileSections corpCode="00126380" />,
    );

    // 로딩이 끝날 때까지 기다린 뒤 비어 있는지 확인한다
    await vi.waitFor(() =>
      expect(container.querySelector('[role="status"]')).toBeNull(),
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('404 는 조용히 전체 미노출한다', async () => {
    stubProfile(null, 404, 'COMPANY_NOT_FOUND');

    const { container } = render(
      <CompanyProfileSections corpCode="99999999" />,
    );

    await vi.waitFor(() =>
      expect(container.querySelector('[role="status"]')).toBeNull(),
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('5xx 는 오류 안내와 다시 시도를 보여준다', async () => {
    stubProfile(null, 500, 'INTERNAL_ERROR');

    render(<CompanyProfileSections corpCode="00126380" />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /사업 정보를 불러오지 못했습니다/,
    );
    expect(
      screen.getByRole('button', { name: '다시 시도' }),
    ).toBeInTheDocument();
  });

  it('세그먼트가 전부 미공시면 사업부 카드만 남고 매출 카드는 없다', async () => {
    stubProfile({
      year: 2025,
      businesses: [],
      segments: [{ code: 'DS', revenue: null, revenueShare: null }],
      totalRevenue: null,
      products: [],
    });

    render(<CompanyProfileSections corpCode="00126380" />);

    expect(
      await screen.findByRole('heading', { name: '사업부' }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: '사업부 매출' }),
    ).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `npx vitest run src/features/company-profile/CompanyProfileSections.test.tsx`
Expected: FAIL (import 실패)

- [ ] **Step 3: 구현**

`frontend/src/features/company-profile/CompanyProfileSections.tsx`:

```tsx
import { InlineNotice } from '../../components/common/InlineNotice';
import { BusinessCard } from './BusinessCard';
import { ProductCard } from './ProductCard';
import { SegmentCard } from './SegmentCard';
import { SegmentRevenueCard } from './SegmentRevenueCard';
import { useCompanyProfile } from './useCompanyProfile';

interface CompanyProfileSectionsProps {
  corpCode: string;
}

/**
 * 기업 개요의 조건부 영역. 데이터가 있는 카드만 노출한다.
 * - 404 또는 전 배열 empty → 전체 미노출 (기본정보 카드만 남는다)
 * - 그 외 오류 → InlineNotice + 다시 시도
 */
export function CompanyProfileSections({
  corpCode,
}: CompanyProfileSectionsProps) {
  const { state, retry } = useCompanyProfile(corpCode);

  if (state.status === 'loading') {
    return (
      <div
        aria-busy="true"
        className="grid gap-6 lg:grid-cols-2"
        role="status"
      >
        <span className="sr-only">사업 정보를 불러오는 중입니다</span>
        <div className="min-h-48 animate-pulse rounded-3xl border border-slate-200 bg-slate-50" />
        <div className="min-h-48 animate-pulse rounded-3xl border border-slate-200 bg-slate-50" />
      </div>
    );
  }

  if (state.status === 'error') {
    if (state.error.code === 'COMPANY_NOT_FOUND') {
      return null;
    }
    return (
      <InlineNotice onRetry={retry}>
        사업 정보를 불러오지 못했습니다. {state.error.message}
      </InlineNotice>
    );
  }

  const { businesses, segments, products, totalRevenue } = state.data;
  const hasRevenue = segments.some((s) => s.revenue !== null);
  const hasAny =
    businesses.length > 0 || segments.length > 0 || products.length > 0;

  if (!hasAny) {
    return null;
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {businesses.length > 0 && <BusinessCard items={businesses} />}
      {segments.length > 0 && <SegmentCard segments={segments} />}
      {products.length > 0 && <ProductCard items={products} />}
      {hasRevenue && (
        <SegmentRevenueCard segments={segments} totalRevenue={totalRevenue} />
      )}
    </div>
  );
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `npx vitest run src/features/company-profile/CompanyProfileSections.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/company-profile/CompanyProfileSections.tsx frontend/src/features/company-profile/CompanyProfileSections.test.tsx
git commit -m "feat: [S15P21A504-102] 프로필 조건부 섹션 결측 처리"
```

---

### Task 7: 탭 라우트 재편 + 페이지 조립 (101)

**Files:**
- Modify: `frontend/src/app/router.tsx`
- Modify: `frontend/src/pages/company-detail/CompanyDetailPage.tsx` (전면 재작성)
- Create: `frontend/src/pages/company-detail/CompanyTabNav.tsx`
- Create: `frontend/src/pages/company-detail/CompanyOverviewTab.tsx`
- Create: `frontend/src/pages/company-detail/CompanyComparisonTab.tsx`
- Modify: `frontend/src/pages/company-detail/CompanyDetailPage.test.tsx`

**Interfaces:**
- Consumes: `useCompanyDetail`·`CompanyDetailState`(기존), `CompanyBasicInfoCard`(Task 3), `CompanyProfileSections`(Task 6), `IndustryComparisonSection`(기존), `AppHeader`(기존 — Task 8 에서 props 추가 예정이므로 여기서는 무인자 사용 유지)
- Produces:
  - 라우트: `/companies/:companyId` → index 는 `overview` 로 redirect, children `overview`·`comparison`
  - `interface CompanyDetailOutletContext { corpCode: string; detailState: CompanyDetailState; retryDetail: () => void }` — `CompanyDetailPage.tsx` 에서 export, 탭들이 `useOutletContext` 로 소비
  - KeyMetrics·FinancialTrend import 는 페이지에서 제거 (파일·테스트는 유지)

- [ ] **Step 1: 기존 테스트를 새 구조로 갱신 (실패하는 테스트)**

`frontend/src/pages/company-detail/CompanyDetailPage.test.tsx` 전체를 다음으로 교체:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RouterProvider } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { createAppRouter } from '../../app/router';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

const detailBody = {
  success: true,
  data: {
    corpCode: '00126380',
    corpName: '삼성전자',
    stockCode: '005930',
    industryCode: '26',
    industryName: '전자 부품, 컴퓨터, 영상, 음향 및 통신장비 제조업',
    market: 'KOSPI',
    ceo: '전영현',
    establishedDate: '1969-01-13',
    address: '경기도 수원시 영통구 삼성로 129',
    homepageUrl: 'https://www.samsung.com',
    dataYear: 2025,
  },
};

const profileBody = {
  success: true,
  data: {
    year: 2025,
    businesses: ['반도체'],
    segments: [{ code: 'DS', revenue: 1000, revenueShare: 100 }],
    totalRevenue: 1000,
    products: ['HBM'],
  },
};

const emptyComparison = {
  success: true,
  data: { year: 2025, industry: null, metrics: [], companies: [] },
};

/** 상세 레이아웃·탭이 부르는 API 를 URL 로 구분해 응답한다. */
const stubFetchByUrl = (
  detail: Response | (() => Response) = () => json(detailBody),
) =>
  vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/profile')) {
      return Promise.resolve(json(profileBody));
    }
    if (url.includes('/industry-comparison')) {
      return Promise.resolve(json(emptyComparison));
    }
    return Promise.resolve(typeof detail === 'function' ? detail() : detail);
  });

const renderAt = (path: string) =>
  render(<RouterProvider router={createAppRouter([path])} />);

describe('CompanyDetailPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('/companies/:id 는 기업 개요 탭으로 리다이렉트한다', async () => {
    vi.stubGlobal('fetch', stubFetchByUrl());

    renderAt('/companies/00126380');

    expect(
      await screen.findByRole('heading', { level: 1, name: '삼성전자' }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole('heading', { name: '주요 사업' }),
    ).toBeInTheDocument();
    // 데이터 기준 칩
    expect(screen.getByText('데이터 기준: 2025')).toBeInTheDocument();
  });

  it('탭 버튼으로 산업 비교 탭에 이동한다', async () => {
    vi.stubGlobal('fetch', stubFetchByUrl());
    const user = userEvent.setup();

    renderAt('/companies/00126380');
    await screen.findByRole('heading', { level: 1, name: '삼성전자' });

    await user.click(screen.getByRole('link', { name: '산업 비교' }));

    expect(
      await screen.findByRole('heading', { name: /산업 비교/ }),
    ).toBeInTheDocument();
  });

  it('미구현 탭은 비활성 버튼으로 표시된다', async () => {
    vi.stubGlobal('fetch', stubFetchByUrl());

    renderAt('/companies/00126380');
    await screen.findByRole('heading', { level: 1, name: '삼성전자' });

    for (const label of ['성장 분석', '집중 분야', '최근 이슈']) {
      expect(screen.getByRole('button', { name: label })).toBeDisabled();
    }
  });

  it('기본정보 API 가 실패해도 페이지는 유지된다 (F-31)', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetchByUrl(() =>
        json(
          { success: false, error: { code: 'INTERNAL_ERROR', message: 'x' } },
          500,
        ),
      ),
    );

    renderAt('/companies/00126380');

    expect(
      await screen.findByRole('heading', { level: 1, name: '기업 분석' }),
    ).toBeInTheDocument();
    // 조건부 섹션은 별개 요청이라 정상 표시된다
    expect(
      await screen.findByRole('heading', { name: '주요 사업' }),
    ).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `npx vitest run src/pages/company-detail/CompanyDetailPage.test.tsx`
Expected: FAIL (아직 단일 페이지 구조 — 주요 사업 헤딩 없음)

- [ ] **Step 3: 구현**

`frontend/src/pages/company-detail/CompanyTabNav.tsx`:

```tsx
import { NavLink } from 'react-router-dom';

const TABS = [
  { label: '기업 개요', to: 'overview' },
  { label: '성장 분석', to: null },
  { label: '집중 분야', to: null },
  { label: '산업 비교', to: 'comparison' },
  { label: '최근 이슈', to: null },
] as const;

/** 상세 페이지 탭. to 가 없는 탭은 화면 미구현이라 비활성 버튼으로만 보여준다. */
export function CompanyTabNav() {
  return (
    <nav aria-label="기업 분석 탭">
      <ul className="flex flex-wrap gap-2">
        {TABS.map(({ label, to }) => (
          <li key={label}>
            {to ? (
              <NavLink
                className={({ isActive }) =>
                  `inline-block rounded-full px-4 py-2 text-sm font-bold transition ${
                    isActive
                      ? 'bg-blue-600 text-white'
                      : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-100'
                  }`
                }
                to={to}
              >
                {label}
              </NavLink>
            ) : (
              <button
                className="inline-block cursor-not-allowed rounded-full bg-white px-4 py-2 text-sm font-bold text-slate-300 ring-1 ring-slate-200"
                disabled
                title="준비 중"
                type="button"
              >
                {label}
              </button>
            )}
          </li>
        ))}
      </ul>
    </nav>
  );
}
```

`frontend/src/pages/company-detail/CompanyDetailPage.tsx` 전체 교체:

```tsx
import { Outlet, useParams } from 'react-router-dom';
import { AppHeader } from '../../components/layout/AppHeader';
import {
  useCompanyDetail,
  type CompanyDetailState,
} from '../../features/company-detail/useCompanyDetail';
import { CompanyTabNav } from './CompanyTabNav';

/** 탭 페이지들이 useOutletContext 로 받는 값 */
export interface CompanyDetailOutletContext {
  corpCode: string;
  detailState: CompanyDetailState;
  retryDetail: () => void;
}

/** 기업 상세 레이아웃. 헤더 + 탭 네비 + 탭 콘텐츠(Outlet). */
export function CompanyDetailPage() {
  const { companyId } = useParams();
  const corpCode = companyId ?? '';
  const { state, retry } = useCompanyDetail(corpCode);
  const detail = state.status === 'success' ? state.data : null;

  const context: CompanyDetailOutletContext = {
    corpCode,
    detailState: state,
    retryDetail: retry,
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <AppHeader />

      <main className="mx-auto max-w-7xl px-5 py-8 sm:px-8 lg:px-10 lg:py-10">
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <CompanyTabNav />
          {detail?.dataYear != null && (
            <p className="rounded-full bg-blue-50 px-4 py-2 text-sm font-semibold text-blue-700">
              데이터 기준: {detail.dataYear}
            </p>
          )}
        </div>

        <Outlet context={context} />
      </main>
    </div>
  );
}
```

`frontend/src/pages/company-detail/CompanyOverviewTab.tsx`:

```tsx
import { useOutletContext } from 'react-router-dom';
import { CompanyBasicInfoCard } from '../../features/company-profile/CompanyBasicInfoCard';
import { CompanyProfileSections } from '../../features/company-profile/CompanyProfileSections';
import type { CompanyDetailOutletContext } from './CompanyDetailPage';

/** 기업 개요 탭: 기본정보 카드 + 조건부 사업정보 섹션 */
export function CompanyOverviewTab() {
  const { corpCode, detailState } =
    useOutletContext<CompanyDetailOutletContext>();

  return (
    <div className="space-y-8">
      <CompanyBasicInfoCard corpCode={corpCode} state={detailState} />
      <CompanyProfileSections corpCode={corpCode} />
    </div>
  );
}
```

`frontend/src/pages/company-detail/CompanyComparisonTab.tsx`:

```tsx
import { useOutletContext } from 'react-router-dom';
import { IndustryComparisonSection } from '../../features/industry-comparison/IndustryComparisonSection';
import type { CompanyDetailOutletContext } from './CompanyDetailPage';

/** 산업 비교 탭: 기존 산업 비교 섹션을 그대로 배치한다 */
export function CompanyComparisonTab() {
  const { corpCode } = useOutletContext<CompanyDetailOutletContext>();

  return <IndustryComparisonSection corpCode={corpCode} />;
}
```

`frontend/src/app/router.tsx` 의 routes 배열 교체:

```tsx
import {
  createBrowserRouter,
  createMemoryRouter,
  Navigate,
  type RouteObject,
} from 'react-router-dom';
import { CompanyComparisonTab } from '../pages/company-detail/CompanyComparisonTab';
import { CompanyDetailPage } from '../pages/company-detail/CompanyDetailPage';
import { CompanyOverviewTab } from '../pages/company-detail/CompanyOverviewTab';
import { HomePage } from '../pages/home/HomePage';
import { NotFoundPage } from '../pages/not-found/NotFoundPage';

const routes: RouteObject[] = [
  {
    path: '/',
    element: <HomePage />,
  },
  {
    path: '/companies/:companyId',
    element: <CompanyDetailPage />,
    children: [
      { index: true, element: <Navigate replace to="overview" /> },
      { path: 'overview', element: <CompanyOverviewTab /> },
      { path: 'comparison', element: <CompanyComparisonTab /> },
    ],
  },
  {
    path: '*',
    element: <NotFoundPage />,
  },
];
```

(`createAppRouter` 함수는 그대로 둔다.)

- [ ] **Step 4: 테스트 통과 확인 + 전체 회귀**

Run: `npx vitest run`
Expected: 전체 PASS. `router.test.tsx` 가 기존 단일 라우트를 전제로 깨지면 리다이렉트 기대로 수정한다(예: `/companies/x` 진입 시 최종 경로가 `/companies/x/overview`).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/router.tsx frontend/src/pages/company-detail
git commit -m "feat: [S15P21A504-101] 기업 상세 탭 라우트 재편"
```

---

### Task 8: 상단 헤더 브레드크럼·검색바 (101)

**Files:**
- Modify: `frontend/src/components/layout/AppHeader.tsx`
- Create: `frontend/src/components/layout/HeaderSearch.tsx`
- Modify: `frontend/src/pages/company-detail/CompanyDetailPage.tsx` (AppHeader 에 companyName 전달, 5줄 이내)
- Test: `frontend/src/components/layout/HeaderSearch.test.tsx`

**Interfaces:**
- Consumes: `CompanySearchForm`(기존, `onSearch(keyword)` 콜백), `searchCompanies`(기존 `features/company-search/api.ts`, `(keyword, signal?) => Promise<{ items: Company[]; total: number }>`), `Company`(`types/company.ts`)
- Produces:
  - `AppHeader({ companyName }: { companyName?: string })` — companyName 이 있으면 브레드크럼(홈 > 기업 분석 > {기업명})과 검색바 표시. 없으면 기존 모습 유지
  - `HeaderSearch()` — 검색 제출 시 드롭다운으로 결과를 보여주고, 기업 선택 시 `/companies/{corpCode}/overview` 로 이동

- [ ] **Step 1: 실패하는 테스트 작성**

`frontend/src/components/layout/HeaderSearch.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {
  createMemoryRouter,
  RouterProvider,
  useLocation,
} from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { HeaderSearch } from './HeaderSearch';

const json = (body: unknown) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });

function LocationProbe() {
  const location = useLocation();
  return <p data-testid="location">{location.pathname}</p>;
}

const renderWithRouter = () => {
  const router = createMemoryRouter([
    {
      path: '*',
      element: (
        <>
          <HeaderSearch />
          <LocationProbe />
        </>
      ),
    },
  ]);
  return render(<RouterProvider router={router} />);
};

describe('HeaderSearch', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('검색 후 기업을 선택하면 기업 개요로 이동한다', async () => {
    vi.stubEnv('VITE_API_MOCK', 'false');
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          json({
            success: true,
            data: {
              items: [
                {
                  corpCode: '00164779',
                  corpName: 'SK하이닉스',
                  stockCode: '000660',
                  industryCode: '26',
                  industryName: '반도체 제조업',
                },
              ],
              total: 1,
            },
          }),
        ),
      ),
    );
    const user = userEvent.setup();

    renderWithRouter();

    await user.type(screen.getByRole('searchbox'), '하이닉스');
    await user.click(screen.getByRole('button', { name: '검색' }));
    await user.click(
      await screen.findByRole('option', { name: /SK하이닉스/ }),
    );

    expect(screen.getByTestId('location')).toHaveTextContent(
      '/companies/00164779/overview',
    );
  });

  it('결과가 없으면 안내 문구를 보여준다', async () => {
    vi.stubEnv('VITE_API_MOCK', 'false');
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          json({ success: true, data: { items: [], total: 0 } }),
        ),
      ),
    );
    const user = userEvent.setup();

    renderWithRouter();

    await user.type(screen.getByRole('searchbox'), '없는기업');
    await user.click(screen.getByRole('button', { name: '검색' }));

    expect(
      await screen.findByText('검색 결과가 없습니다'),
    ).toBeInTheDocument();
  });
});
```

주의: `searchCompanies` 도 모듈 상수 `USE_MOCK` 을 쓰고 있다면(`features/company-search/api.ts` 확인) Task 1 과 같은 방식으로 호출 시점 평가 `useMock()` 으로 바꾼다. 이미 함수형이면 그대로 둔다.

- [ ] **Step 2: 테스트 실패 확인**

Run: `npx vitest run src/components/layout/HeaderSearch.test.tsx`
Expected: FAIL (import 실패)

- [ ] **Step 3: 구현**

`frontend/src/components/layout/HeaderSearch.tsx`:

```tsx
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { searchCompanies } from '../../features/company-search/api';
import { CompanySearchForm } from '../../features/company-search/CompanySearchForm';
import type { Company } from '../../types/company';

type SearchStatus = 'idle' | 'loading' | 'success' | 'error';

/** 헤더용 컴팩트 검색. 제출 시 드롭다운으로 결과를 보여주고 선택하면 기업 개요로 이동한다. */
export function HeaderSearch() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<SearchStatus>('idle');
  const [companies, setCompanies] = useState<Company[]>([]);
  const inFlight = useRef<AbortController | null>(null);

  useEffect(() => () => inFlight.current?.abort(), []);

  const runSearch = async (keyword: string) => {
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    setStatus('loading');

    try {
      const result = await searchCompanies(keyword, controller.signal);
      if (controller.signal.aborted) {
        return;
      }
      setCompanies(result.items);
      setStatus('success');
    } catch {
      if (controller.signal.aborted) {
        return;
      }
      setCompanies([]);
      setStatus('error');
    }
  };

  const close = () => {
    setStatus('idle');
    setCompanies([]);
  };

  const select = (company: Company) => {
    close();
    navigate(`/companies/${company.corpCode}/overview`);
  };

  return (
    <div className="relative w-full max-w-md">
      <CompanySearchForm onSearch={runSearch} />

      {status !== 'idle' && (
        <div className="absolute inset-x-0 top-full z-20 mt-2 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-lg">
          {status === 'loading' && (
            <p className="px-5 py-4 text-sm text-slate-500" role="status">
              검색 중…
            </p>
          )}
          {status === 'error' && (
            <p className="px-5 py-4 text-sm text-amber-900" role="alert">
              검색에 실패했습니다. 잠시 후 다시 시도해 주세요.
            </p>
          )}
          {status === 'success' &&
            (companies.length === 0 ? (
              <p className="px-5 py-4 text-sm text-slate-500">
                검색 결과가 없습니다
              </p>
            ) : (
              <ul role="listbox" aria-label="검색 결과">
                {companies.map((company) => (
                  <li key={company.corpCode}>
                    <button
                      className="flex w-full items-baseline gap-3 px-5 py-3 text-left transition hover:bg-slate-50"
                      onClick={() => select(company)}
                      role="option"
                      aria-selected="false"
                      type="button"
                    >
                      <span className="text-sm font-bold text-slate-900">
                        {company.corpName}
                      </span>
                      <span className="truncate text-xs text-slate-500">
                        {company.industryName ?? ''}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            ))}
        </div>
      )}
    </div>
  );
}
```

`frontend/src/components/layout/AppHeader.tsx` 교체:

```tsx
import { Link } from 'react-router-dom';
import { HeaderSearch } from './HeaderSearch';

interface AppHeaderProps {
  /** 있으면 브레드크럼과 검색바를 보여준다 (기업 상세 화면용) */
  companyName?: string;
}

export function AppHeader({ companyName }: AppHeaderProps) {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-5 sm:px-8 lg:px-10">
        <Link
          className="shrink-0 text-lg font-extrabold tracking-tight text-slate-950"
          to="/"
        >
          기업 변화 분석
        </Link>

        {companyName ? (
          <>
            <nav aria-label="브레드크럼" className="hidden min-w-0 md:block">
              <ol className="flex items-center gap-2 text-sm text-slate-500">
                <li>
                  <Link className="transition hover:text-slate-900" to="/">
                    홈
                  </Link>
                </li>
                <li aria-hidden="true">/</li>
                <li className="truncate font-bold text-blue-600">
                  {companyName}
                </li>
              </ol>
            </nav>
            <div className="ml-auto flex min-w-0 flex-1 justify-end">
              <HeaderSearch />
            </div>
          </>
        ) : (
          <Link
            className="ml-auto rounded-lg px-3 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-100 hover:text-slate-950"
            to="/"
          >
            다른 기업 검색
          </Link>
        )}
      </div>
    </header>
  );
}
```

`frontend/src/pages/company-detail/CompanyDetailPage.tsx` 의 `<AppHeader />` 를 다음으로 변경:

```tsx
<AppHeader companyName={detail?.corpName} />
```

- [ ] **Step 4: 테스트 통과 확인 + 전체 회귀 + 린트 + 빌드**

Run: `npx vitest run`
Expected: 전체 PASS
Run: `npm run lint`
Expected: 오류 없음
Run: `npm run build`
Expected: 성공

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/layout frontend/src/pages/company-detail/CompanyDetailPage.tsx
git commit -m "feat: [S15P21A504-101] 상단 헤더 브레드크럼·검색바 추가"
```

---

## 완료 확인 (Done 대조)

- 실제 API 데이터 표시 → Task 1·2 (계약 기준 연동, mock 은 VITE_API_MOCK 규칙으로 분리)
- 조건부 데이터 있을 때만 노출 → Task 6
- 데이터 없음 상태 처리 → Task 3(정보 없음)·Task 5(미공시)·Task 6(섹션 미노출)
- 기존 검색 기업과 정확하게 연결 → Task 7(리다이렉트)·Task 8(헤더 검색)

수동 확인: `npm run dev` 후 `/companies/00126380`(풀 데이터) · `/companies/90000002`(일부 결측) · `/companies/90000004`(조건부 전체 미노출) 세 경로를 브라우저로 확인한다.

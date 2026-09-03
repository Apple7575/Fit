import { render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import { fetchAllActivities, fetchEmployeeTrend } from './api';
import { DirectionCard } from './DirectionCard';
import { buildEvidenceRows } from './evidence';
import { EvidenceCard } from './EvidenceCard';
import { FocusSummaryCard } from './FocusSummaryCard';
import type { ActivitiesState, FocusState, WorkforceState } from './hooks';
import { InvestmentTimelineCard } from './InvestmentTimelineCard';
import { RndCard } from './RndCard';
import { pickSummaryChips } from './summaryChips';
import type { CompanyFocus, InvestmentActivity, WorkforceChange } from './types';
import { WorkforceCard } from './WorkforceCard';

const focusData: CompanyFocus = {
  year: 2025,
  direction: {
    newBusiness: ['AI 반도체', '시스템LSI'],
    keywords: ['HBM', '2nm GAA', 'AI 반도체'],
    strategyChange: '메모리 중심 → 시스템 반도체 & 파운드리 확대',
  },
  rnd: { expense: 34_100_000_000_000, growthRate: 24.5, revenueRatio: 9.0, fields: ['HBM', '파운드리'] },
};
const focusOk: FocusState = { status: 'success', data: focusData };

const activities: InvestmentActivity[] = [
  { year: 2025, type: 'facility', field: '파운드리', purpose: '평택 P5 라인 건설 투자', amount: 23_000_000_000_000 },
  { year: 2024, type: 'corporate_invest', field: 'AI 반도체', purpose: 'ASML 지분 인수', amount: 1_100_000_000_000 },
  { year: 2023, type: 'ma', field: '전장', purpose: null, amount: null },
];
const activitiesOk: ActivitiesState = { status: 'success', data: activities };

const workforceData: WorkforceChange = {
  year: 2025,
  employeeTotalChange: 3050,
  segments: [
    { name: 'DS', revenue: 1, revenueShare: 58.0, employeeChange: 4015 },
    { name: 'DX', revenue: 1, revenueShare: 42.0, employeeChange: 2120 },
    { name: 'SDC', revenue: null, revenueShare: null, employeeChange: null },
  ],
};
const workforceOk: WorkforceState = { status: 'success', data: workforceData };

describe('FocusSummaryCard', () => {
  it('shows up to three unique chips, the strategy sentence and an AI badge', () => {
    render(<FocusSummaryCard state={focusOk} />);

    const chips = within(screen.getByRole('list', { name: '집중 분야 키워드' })).getAllByRole('listitem');
    expect(chips.map((c) => c.textContent)).toEqual(['HBM', '2nm GAA', 'AI 반도체']);
    expect(screen.getByText('메모리 중심 → 시스템 반도체 & 파운드리 확대')).toBeInTheDocument();
    expect(screen.getByText('AI 분석')).toBeInTheDocument();
  });

  it('hides itself when the direction is missing or the request failed', () => {
    const { container, unmount } = render(
      <FocusSummaryCard state={{ status: 'success', data: { ...focusData, direction: null } }} />,
    );
    expect(container).toBeEmptyDOMElement();
    unmount();
    const second = render(
      <FocusSummaryCard state={{ status: 'error', error: new ApiError(404, 'X', 'x') }} />,
    );
    expect(second.container).toBeEmptyDOMElement();
  });

  it('dedupes chips across keywords and new business', () => {
    expect(pickSummaryChips(['a', 'b'], ['b', 'c', 'd'])).toEqual(['a', 'b', 'c']);
  });
});

describe('DirectionCard / RndCard', () => {
  it('lists the three direction rows and the R&D figures with data badge', () => {
    render(
      <>
        <DirectionCard state={focusOk} />
        <RndCard state={focusOk} />
      </>,
    );

    expect(screen.getByText('신규 사업')).toBeInTheDocument();
    expect(screen.getByText('AI 반도체, 시스템LSI')).toBeInTheDocument();
    expect(screen.getByText('핵심 사업 키워드')).toBeInTheDocument();
    expect(screen.getByText('전략 변화')).toBeInTheDocument();

    expect(screen.getByRole('heading', { name: 'R&D' })).toBeInTheDocument();
    expect(screen.getByText('34.1조 원')).toBeInTheDocument();
    expect(screen.getByText('+24.5%')).toBeInTheDocument();
    expect(screen.getByText('9.0%')).toBeInTheDocument();
    expect(within(screen.getByRole('list', { name: '주요 연구 분야' })).getAllByRole('listitem')).toHaveLength(2);
    expect(screen.getByText('실제 데이터')).toBeInTheDocument();
  });

  it('shows 미제공 for missing R&D numbers and hides cards without data', () => {
    render(
      <RndCard
        state={{
          status: 'success',
          data: { ...focusData, rnd: { expense: null, growthRate: null, revenueRatio: 5, fields: [] } },
        }}
      />,
    );
    expect(screen.getAllByText('미제공')).toHaveLength(2);

    const { container } = render(
      <DirectionCard state={{ status: 'success', data: { ...focusData, direction: null } }} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});

describe('InvestmentTimelineCard', () => {
  it('renders a mixed-type timeline newest first with amounts or 금액 미공시', () => {
    render(<InvestmentTimelineCard onRetry={() => {}} state={activitiesOk} />);

    const items = screen.getAllByRole('listitem');
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent('2025');
    expect(items[0]).toHaveTextContent('설비투자');
    expect(items[0]).toHaveTextContent('평택 P5 라인 건설 투자');
    expect(items[0]).toHaveTextContent('약 23조 원');
    expect(items[1]).toHaveTextContent('타법인 출자');
    expect(items[2]).toHaveTextContent('금액 미공시');
    expect(items[2]).toHaveTextContent('전장');
  });

  it('explains an empty timeline', () => {
    render(<InvestmentTimelineCard onRetry={() => {}} state={{ status: 'success', data: [] }} />);
    expect(screen.getByText('확인 가능한 투자·M&A 공시가 없습니다')).toBeInTheDocument();
  });
});

describe('WorkforceCard', () => {
  it('draws the headcount bars and lists segment changes with the total', () => {
    render(
      <WorkforceCard
        onRetryTrend={() => {}}
        onRetryWorkforce={() => {}}
        trend={{
          status: 'success',
          data: [
            { year: 2021, value: 117_909 },
            { year: 2022, value: 124_071 },
            { year: 2023, value: null },
            { year: 2024, value: 133_950 },
            { year: 2025, value: 137_000 },
          ],
        }}
        workforce={workforceOk}
      />,
    );

    const chart = screen.getByRole('img', { name: '전체 직원 수 5년 추이' });
    expect(within(chart).getAllByTestId('bar')).toHaveLength(4);
    expect(within(chart).getByText('미제공')).toBeInTheDocument();
    expect(within(chart).getByText('137,000')).toBeInTheDocument();

    const list = within(screen.getByRole('list', { name: '사업부별 직원 순증감' }));
    expect(list.getByText('+4,015명')).toBeInTheDocument();
    expect(list.getByText('미제공')).toBeInTheDocument();
    expect(screen.getByText('+3,050명')).toBeInTheDocument();
  });
});

describe('EvidenceCard', () => {
  it('builds fact rows only from data that exists', () => {
    const rows = buildEvidenceRows(focusData, activities, workforceData);
    expect(rows.map((r) => r.label)).toEqual(['사업부 매출 비중', 'R&D 투자', '신규 투자', '인력 증가']);
    expect(rows[0].body).toBe('DS 부문(58.0%), DX 부문(42.0%)');
    expect(rows[1].body).toBe('R&D 비용 34.1조 원으로 전년 대비 +24.5%');
    expect(rows[2].body).toContain('평택 P5 라인 건설 투자(2025)');
    expect(rows[3].body).toBe('전사 인원 +3,050명, DS·DX 중심 인력 변화');

    expect(buildEvidenceRows(null, [], { year: null, employeeTotalChange: null, segments: [] })).toEqual([]);
  });

  it('renders the rows and hides itself when there is nothing to say', () => {
    render(<EvidenceCard activities={activitiesOk} focus={focusOk} workforce={workforceOk} />);
    expect(screen.getByRole('heading', { name: '판단 근거' })).toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(4);

    const { container } = render(
      <EvidenceCard
        activities={{ status: 'error', error: new ApiError(500, 'X', 'x') }}
        focus={{ status: 'error', error: new ApiError(404, 'X', 'x') }}
        workforce={{ status: 'success', data: { year: null, employeeTotalChange: null, segments: [] } }}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

describe('focus fetchers', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('fetchAllActivities calls all four types and merges newest first', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const type = new URL(url, 'http://x').searchParams.get('type');
      return Promise.resolve(
        json({
          success: true,
          data: {
            items:
              type === 'ma'
                ? [{ year: 2023, type: 'ma', field: '전장', purpose: '인수', amount: 1 }]
                : type === 'facility'
                  ? [{ year: 2025, type: 'facility', field: '파운드리', purpose: '증설', amount: 2 }]
                  : [],
          },
        }),
      );
    });
    vi.stubGlobal('fetch', fetchMock);

    const items = await fetchAllActivities('00126380');
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(items.map((i) => i.year)).toEqual([2025, 2023]);
  });

  it('fetchEmployeeTrend requests keys=employee_count and fills missing years with null', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      json({
        success: true,
        data: {
          range: { from: 2021, to: 2025 },
          series: [
            { key: 'employee_count', points: [{ year: 2021, value: 100 }, { year: 2025, value: 120 }] },
          ],
        },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const points = await fetchEmployeeTrend('00126380');
    expect(String(fetchMock.mock.calls[0][0])).toContain('keys=employee_count');
    expect(points).toEqual([
      { year: 2021, value: 100 },
      { year: 2022, value: null },
      { year: 2023, value: null },
      { year: 2024, value: null },
      { year: 2025, value: 120 },
    ]);
  });
});

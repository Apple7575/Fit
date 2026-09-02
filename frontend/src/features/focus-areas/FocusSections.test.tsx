import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ActivitiesSection } from './ActivitiesSection';
import { FocusDirectionSection } from './FocusDirectionSection';
import { WorkforceSection } from './WorkforceSection';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

const ok = (data: unknown) => json({ success: true, data });

describe('ActivitiesSection', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('fetches facility events first and refetches when the type changes', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      return Promise.resolve(
        url.includes('type=ma')
          ? ok({
              items: [
                { year: 2023, type: 'ma', field: '전장', purpose: '사업 인수', amount: 12_000_000_000_000 },
              ],
            })
          : ok({
              items: [
                { year: 2025, type: 'facility', field: '파운드리', purpose: '테일러 공장', amount: 23_000_000_000_000 },
                { year: 2024, type: 'facility', field: 'HBM', purpose: null, amount: null },
              ],
            }),
      );
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<ActivitiesSection corpCode="00126380" />);

    expect(await screen.findByText('파운드리')).toBeInTheDocument();
    expect(screen.getByText('23조 원')).toBeInTheDocument();
    expect(screen.getByText('금액 미공시')).toBeInTheDocument();
    expect(screen.getByText('목적 정보 없음')).toBeInTheDocument();
    expect(String(fetchMock.mock.calls[0][0])).toContain('/activities?type=facility');
    expect(screen.getByText('실제 데이터')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('radio', { name: 'M&A' }));

    expect(await screen.findByText('전장')).toBeInTheDocument();
    expect(String(fetchMock.mock.calls[1][0])).toContain('type=ma');
  });

  it('explains an empty list per type instead of showing 0', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok({ items: [] })));

    render(<ActivitiesSection corpCode="A" />);

    expect(
      await screen.findByText('확인 가능한 설비투자 이벤트가 없습니다'),
    ).toBeInTheDocument();
  });

  it('offers a retry after a server error', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        json({ success: false, error: { code: 'INTERNAL_ERROR', message: '오류' } }, 500),
      )
      .mockResolvedValueOnce(ok({ items: [] }));
    vi.stubGlobal('fetch', fetchMock);

    render(<ActivitiesSection corpCode="A" />);

    expect(await screen.findByRole('alert')).toHaveTextContent('투자 이벤트를 불러오지 못했습니다');
    fireEvent.click(screen.getByRole('button', { name: '다시 시도' }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });
});

describe('WorkforceSection', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('shows the company-wide change and each segment, marking missing values', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        ok({
          year: 2025,
          employeeTotalChange: 3050,
          segments: [
            { name: 'DS', revenue: 232_000_000_000_000, revenueShare: 58.0, employeeChange: 4015 },
            { name: 'SDC', revenue: null, revenueShare: null, employeeChange: 248 },
            { name: 'DX', revenue: 1, revenueShare: 1, employeeChange: null },
          ],
        }),
      ),
    );

    render(<WorkforceSection corpCode="00126380" />);

    expect(await screen.findByText('+3,050명')).toBeInTheDocument();
    const list = screen.getByRole('list', { name: '사업부별 직원 순증감' });
    expect(within(list).getAllByRole('listitem')).toHaveLength(3);
    expect(within(list).getByText('+4,015명')).toBeInTheDocument();
    expect(within(list).getByText('매출 미공시')).toBeInTheDocument();
    expect(within(list).getByText('미제공')).toBeInTheDocument();
  });

  it('explains missing segments and a missing total', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(ok({ year: 2025, employeeTotalChange: null, segments: [] })),
    );

    render(<WorkforceSection corpCode="A" />);

    expect(
      await screen.findByText('확인 가능한 사업부별 직원현황이 없습니다'),
    ).toBeInTheDocument();
    expect(screen.getByText('미제공')).toBeInTheDocument();
  });
});

describe('FocusDirectionSection', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('renders the AI direction with an AI badge and the R&D figures with a data badge', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        ok({
          year: 2025,
          direction: {
            newBusiness: ['AI 반도체'],
            keywords: ['HBM'],
            strategyChange: '메모리 중심 → 파운드리 확대',
          },
          rnd: { expense: 34_100_000_000_000, growthRate: 24.5, revenueRatio: 9.0, fields: ['HBM'] },
        }),
      ),
    );

    render(<FocusDirectionSection corpCode="00126380" />);

    expect(await screen.findByRole('heading', { name: '사업 방향' })).toBeInTheDocument();
    expect(screen.getByText('AI 분석')).toBeInTheDocument();
    expect(screen.getByText('메모리 중심 → 파운드리 확대')).toBeInTheDocument();
    expect(within(screen.getByRole('list', { name: '신규 사업' })).getByText('AI 반도체')).toBeInTheDocument();

    expect(screen.getByRole('heading', { name: '연구개발(R&D)' })).toBeInTheDocument();
    expect(screen.getByText('실제 데이터')).toBeInTheDocument();
    expect(screen.getByText('34조 1,000억 원')).toBeInTheDocument();
    expect(screen.getByText('+24.5%')).toBeInTheDocument();
    expect(screen.getByText('9.0%')).toBeInTheDocument();
  });

  it('renders nothing on 404 or when both blocks are empty', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('Not Found', { status: 404 })));
    const first = render(<FocusDirectionSection corpCode="A" />);
    await waitFor(() => expect(first.container.querySelector('[role="status"]')).toBeNull());
    expect(first.container).toBeEmptyDOMElement();
    first.unmount();

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok({ year: 2025, direction: null, rnd: null })));
    const second = render(<FocusDirectionSection corpCode="B" />);
    await waitFor(() => expect(second.container.querySelector('[role="status"]')).toBeNull());
    expect(second.container).toBeEmptyDOMElement();
  });

  it('shows only the block that has data', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        ok({ year: 2025, direction: null, rnd: { expense: null, growthRate: null, revenueRatio: 5, fields: [] } }),
      ),
    );

    render(<FocusDirectionSection corpCode="C" />);

    expect(await screen.findByRole('heading', { name: '연구개발(R&D)' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '사업 방향' })).not.toBeInTheDocument();
    expect(screen.getAllByText('미제공')).toHaveLength(2);
  });

  it('shows an error notice for a server failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        json({ success: false, error: { code: 'INTERNAL_ERROR', message: '오류' } }, 500),
      ),
    );

    render(<FocusDirectionSection corpCode="D" />);

    expect(await screen.findByRole('alert')).toHaveTextContent('사업 방향 정보를 불러오지 못했습니다');
  });
});

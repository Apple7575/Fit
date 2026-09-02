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

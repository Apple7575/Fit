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

import { render, screen } from '@testing-library/react';
import { RouterProvider } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { createAppRouter } from './router';

const renderRoute = (path: string) => {
  render(<RouterProvider router={createAppRouter([path])} />);
};

describe('application routes', () => {
  it('renders the company search home at the root path', () => {
    renderRoute('/');

    expect(
      screen.getByRole('heading', { name: '기업 검색' }),
    ).toBeInTheDocument();
  });

  it('renders the selected company identifier on the detail route', () => {
    renderRoute('/companies/005930');

    expect(
      screen.getByRole('heading', { name: '기업 상세' }),
    ).toBeInTheDocument();
    expect(screen.getByText('기업 코드: 005930')).toBeInTheDocument();
  });

  it('renders a not-found page for unknown paths', () => {
    renderRoute('/unknown');

    expect(
      screen.getByRole('heading', { name: '페이지를 찾을 수 없습니다' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '홈으로 돌아가기' })).toHaveAttribute(
      'href',
      '/',
    );
  });
});

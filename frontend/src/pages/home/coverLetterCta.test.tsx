import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useAuth } from '../../features/auth/AuthProvider';
import { useCoverLetterCta } from './coverLetterCta';

vi.mock('../../features/auth/AuthProvider', () => ({ useAuth: vi.fn() }));

const mockedAuth = vi.mocked(useAuth);

function Probe() {
  const cta = useCoverLetterCta();
  return <a href={cta.to}>{cta.label}</a>;
}

describe('useCoverLetterCta', () => {
  it('invites a guest to write without logging in', () => {
    mockedAuth.mockReturnValue({ user: null } as never);

    render(<Probe />);

    expect(screen.getByRole('link', { name: '로그인 없이 자소서 써 보기' })).toHaveAttribute(
      'href',
      '/cover-letters/new',
    );
  });

  it('sends a signed-in visitor to their own cover letters', () => {
    mockedAuth.mockReturnValue({ user: { id: 1, email: 'a@b.com', nickname: '세은' } } as never);

    render(<Probe />);

    const link = screen.getByRole('link', { name: '자소서 쓰러 가기' });
    expect(link).toHaveAttribute('href', '/cover-letters');
    expect(screen.queryByText(/로그인 없이/)).not.toBeInTheDocument();
  });
});

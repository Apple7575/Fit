import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AuthButtons } from './AuthButtons';
import { useAuth } from './AuthProvider';

vi.mock('./AuthProvider', () => ({ useAuth: vi.fn() }));

const renderButtons = () =>
  render(
    <MemoryRouter>
      <AuthButtons />
    </MemoryRouter>,
  );

describe('AuthButtons', () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it('shows login and signup links when logged out', () => {
    vi.mocked(useAuth).mockReturnValue({ user: null } as never);

    renderButtons();

    expect(screen.getByRole('link', { name: '로그인' })).toHaveAttribute('href', '/login');
    expect(screen.getByRole('link', { name: '회원가입' })).toHaveAttribute('href', '/signup');
  });

  it('shows the nickname and a logout button when logged in', async () => {
    const logout = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useAuth).mockReturnValue({
      user: { id: 1, email: 'a@b.com', nickname: '민재' },
      logout,
    } as never);

    renderButtons();

    expect(screen.getByRole('link', { name: '민재님' })).toHaveAttribute('href', '/mypage');
    await userEvent.click(screen.getByRole('button', { name: '로그아웃' }));
    expect(logout).toHaveBeenCalled();
  });
});

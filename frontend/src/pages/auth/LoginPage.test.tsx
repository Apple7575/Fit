import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import { useAuth } from '../../features/auth/AuthProvider';
import { LoginPage } from './LoginPage';

vi.mock('../../features/auth/AuthProvider', () => ({
  useAuth: vi.fn(),
}));

const renderPage = () =>
  render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  );

describe('LoginPage', () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it('submits the trimmed email and password', async () => {
    const login = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useAuth).mockReturnValue({ login } as never);

    renderPage();
    await userEvent.type(screen.getByLabelText('이메일'), 'a@b.com');
    await userEvent.type(screen.getByLabelText('비밀번호'), 'secret12');
    await userEvent.click(screen.getByRole('button', { name: '로그인' }));

    // 로그인 유지는 켜지 않은 채로 보낸다 — 공용 PC 를 기본으로 본다
    expect(login).toHaveBeenCalledWith('a@b.com', 'secret12', false);
  });

  it('keeps the session when 로그인 상태 유지 is checked', async () => {
    const login = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useAuth).mockReturnValue({ login } as never);

    renderPage();
    await userEvent.type(screen.getByLabelText('이메일'), 'a@b.com');
    await userEvent.type(screen.getByLabelText('비밀번호'), 'secret12');
    await userEvent.click(screen.getByLabelText('로그인 상태 유지'));
    await userEvent.click(screen.getByRole('button', { name: '로그인' }));

    expect(login).toHaveBeenCalledWith('a@b.com', 'secret12', true);
  });

  it('shows the server message when login fails', async () => {
    const login = vi
      .fn()
      .mockRejectedValue(
        new ApiError(401, 'INVALID_CREDENTIALS', '이메일 또는 비밀번호가 올바르지 않습니다.'),
      );
    vi.mocked(useAuth).mockReturnValue({ login } as never);

    renderPage();
    await userEvent.type(screen.getByLabelText('이메일'), 'a@b.com');
    await userEvent.type(screen.getByLabelText('비밀번호'), 'wrongpass');
    await userEvent.click(screen.getByRole('button', { name: '로그인' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      '이메일 또는 비밀번호가 올바르지 않습니다.',
    );
  });

  it('shows a re-signup hint when the email is not verified', async () => {
    const login = vi
      .fn()
      .mockRejectedValue(new ApiError(403, 'EMAIL_NOT_VERIFIED', '이메일 인증이 필요합니다.'));
    vi.mocked(useAuth).mockReturnValue({ login } as never);

    renderPage();
    await userEvent.type(screen.getByLabelText('이메일'), 'a@b.com');
    await userEvent.type(screen.getByLabelText('비밀번호'), 'secret12');
    await userEvent.click(screen.getByRole('button', { name: '로그인' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('이메일 인증이 필요합니다.');
    expect(screen.getByRole('link', { name: '다시 가입' })).toHaveAttribute('href', '/signup');
  });
});

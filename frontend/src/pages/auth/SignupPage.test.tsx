import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useAuth } from '../../features/auth/AuthProvider';
import { SignupPage } from './SignupPage';

const { navigateMock } = vi.hoisted(() => ({ navigateMock: vi.fn() }));

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => navigateMock };
});
vi.mock('../../features/auth/AuthProvider', () => ({ useAuth: vi.fn() }));

describe('SignupPage', () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it('signs up and moves to the verify-sent page with the email', async () => {
    const signup = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useAuth).mockReturnValue({ signup } as never);

    render(
      <MemoryRouter>
        <SignupPage />
      </MemoryRouter>,
    );
    await userEvent.type(screen.getByLabelText('이메일'), 'a@b.com');
    await userEvent.type(screen.getByLabelText('닉네임'), '민재');
    await userEvent.type(screen.getByLabelText('비밀번호'), 'secret12');
    await userEvent.type(screen.getByLabelText('비밀번호 확인'), 'secret12');
    await userEvent.click(screen.getByRole('button', { name: '회원가입' }));

    expect(signup).toHaveBeenCalledWith('a@b.com', 'secret12', '민재');
    expect(navigateMock).toHaveBeenCalledWith('/verify-sent', { state: { email: 'a@b.com' } });
  });

  it('does not submit when the password confirmation differs', async () => {
    const signup = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useAuth).mockReturnValue({ signup } as never);

    render(
      <MemoryRouter>
        <SignupPage />
      </MemoryRouter>,
    );
    await userEvent.type(screen.getByLabelText('이메일'), 'a@b.com');
    await userEvent.type(screen.getByLabelText('닉네임'), '민재');
    await userEvent.type(screen.getByLabelText('비밀번호'), 'secret12');
    await userEvent.type(screen.getByLabelText('비밀번호 확인'), 'secret13');
    await userEvent.click(screen.getByRole('button', { name: '회원가입' }));

    expect(screen.getByRole('alert')).toHaveTextContent('비밀번호가 일치하지 않습니다.');
    expect(signup).not.toHaveBeenCalled();
    expect(navigateMock).not.toHaveBeenCalled();
  });
});

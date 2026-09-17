import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import { verifyEmail } from '../../features/auth/api';
import { VerifyPage } from './VerifyPage';

vi.mock('../../features/auth/api', () => ({ verifyEmail: vi.fn() }));

const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <VerifyPage />
    </MemoryRouter>,
  );

describe('VerifyPage', () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it('verifies the token and shows a login link', async () => {
    vi.mocked(verifyEmail).mockResolvedValue(undefined);

    renderAt('/verify?token=good-token');

    expect(await screen.findByRole('heading', { name: '이메일 인증 완료' })).toBeInTheDocument();
    // 헤더에도 로그인 링크가 있으므로 본문 안의 버튼형 링크만 본다
    expect(within(screen.getByRole('main')).getByRole('link', { name: '로그인' })).toHaveAttribute(
      'href',
      '/login',
    );
    expect(verifyEmail).toHaveBeenCalledWith('good-token');
  });

  it('shows the server message and a re-signup link on failure', async () => {
    vi.mocked(verifyEmail).mockRejectedValue(
      new ApiError(400, 'VERIFICATION_TOKEN_INVALID', '인증 링크가 유효하지 않거나 만료되었습니다.'),
    );

    renderAt('/verify?token=bad-token');

    expect(await screen.findByRole('alert')).toHaveTextContent(
      '인증 링크가 유효하지 않거나 만료되었습니다.',
    );
    expect(screen.getByRole('link', { name: '다시 가입' })).toHaveAttribute('href', '/signup');
  });

  it('shows an error without calling the API when the token is missing', async () => {
    renderAt('/verify');

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(verifyEmail).not.toHaveBeenCalled();
  });
});

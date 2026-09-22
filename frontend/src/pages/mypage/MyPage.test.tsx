import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import { useAuth } from '../../features/auth/AuthProvider';
import { MyPage } from './MyPage';

vi.mock('../../features/auth/AuthProvider', () => ({ useAuth: vi.fn() }));
vi.mock('../../features/interview/draft', () => ({ clearDraft: vi.fn() }));

const renderPage = () =>
  render(
    <MemoryRouter>
      <MyPage />
    </MemoryRouter>,
  );

describe('MyPage', () => {
  afterEach(() => vi.resetAllMocks());

  it('shows the signed-in member profile', () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { id: 7, email: 'minjae@example.com', nickname: '민재' },
      loading: false,
      withdraw: vi.fn(),
    } as never);

    renderPage();

    expect(screen.getByRole('heading', { name: '내 정보' })).toBeInTheDocument();
    expect(screen.getByText('민재')).toBeInTheDocument();
    expect(screen.getByText('minjae@example.com')).toBeInTheDocument();
  });

  it('requires a password and irreversible-action confirmation before withdrawal', async () => {
    const withdraw = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useAuth).mockReturnValue({
      user: { id: 7, email: 'minjae@example.com', nickname: '민재' },
      loading: false,
      withdraw,
    } as never);

    renderPage();
    await userEvent.click(screen.getByRole('button', { name: '회원탈퇴' }));

    const submit = screen.getByRole('button', { name: '영구 삭제하기' });
    expect(submit).toBeDisabled();

    await userEvent.type(screen.getByLabelText('현재 비밀번호'), 'Password123!');
    await userEvent.click(screen.getByRole('checkbox'));
    await userEvent.click(submit);

    expect(withdraw).toHaveBeenCalledWith('Password123!');
    expect(await screen.findByRole('heading', { name: '탈퇴가 완료되었습니다' })).toBeInTheDocument();
  });

  it('keeps the confirmation form open when the current password is wrong', async () => {
    const withdraw = vi.fn().mockRejectedValue(
      new ApiError(401, 'INVALID_CREDENTIALS', '이메일 또는 비밀번호가 올바르지 않습니다.'),
    );
    vi.mocked(useAuth).mockReturnValue({
      user: { id: 7, email: 'minjae@example.com', nickname: '민재' },
      loading: false,
      withdraw,
    } as never);

    renderPage();
    await userEvent.click(screen.getByRole('button', { name: '회원탈퇴' }));
    await userEvent.type(screen.getByLabelText('현재 비밀번호'), 'wrong');
    await userEvent.click(screen.getByRole('checkbox'));
    await userEvent.click(screen.getByRole('button', { name: '영구 삭제하기' }));

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('현재 비밀번호가 올바르지 않습니다.'),
    );
    expect(screen.getByLabelText('현재 비밀번호')).toBeInTheDocument();
  });
});

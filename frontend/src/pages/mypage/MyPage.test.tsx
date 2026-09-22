import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useAuth } from '../../features/auth/AuthProvider';
import { clearDraft } from '../../features/interview/draft';
import { MyPage } from './MyPage';

vi.mock('../../features/auth/AuthProvider', () => ({ useAuth: vi.fn() }));
vi.mock('../../features/interview/draft', () => ({ clearDraft: vi.fn() }));

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/mypage']}>
      <Routes>
        <Route path="/mypage" element={<MyPage />} />
        <Route path="/" element={<h1>메인 화면</h1>} />
      </Routes>
    </MemoryRouter>,
  );

function mockMember(withdraw = vi.fn().mockResolvedValue(undefined)) {
  vi.mocked(useAuth).mockReturnValue({
    user: { id: 7, email: 'minjae@example.com', nickname: '민재' },
    loading: false,
    withdraw,
  } as never);
  return withdraw;
}

describe('MyPage', () => {
  afterEach(() => vi.restoreAllMocks());

  it('shows a small withdrawal action below the profile card', () => {
    mockMember();
    renderPage();

    expect(screen.getByRole('heading', { name: '내 정보' })).toBeInTheDocument();
    expect(screen.getByText('민재')).toBeInTheDocument();
    expect(screen.getByText('minjae@example.com')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '회원탈퇴' })).toHaveClass('text-xs', 'text-red-500');
    expect(screen.queryByRole('heading', { name: '계정 관리' })).not.toBeInTheDocument();
  });

  it('opens the requested yes-or-no confirmation and closes it with no', async () => {
    const withdraw = mockMember();
    renderPage();

    await userEvent.click(screen.getByRole('button', { name: '회원탈퇴' }));

    const dialog = screen.getByRole('alertdialog', { name: '회원탈퇴' });
    expect(dialog).toHaveTextContent(
      '계정과 저장된 자소서, 면접, 검토 방이 모두 삭제되며 되돌릴 수 없습니다. 정말 탈퇴하시겠습니까?',
    );
    expect(screen.getByRole('button', { name: '네' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '아니오' }));

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    expect(withdraw).not.toHaveBeenCalled();
  });

  it('withdraws with yes, shows completion, and moves to the main page', async () => {
    const withdraw = mockMember();
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    renderPage();

    await userEvent.click(screen.getByRole('button', { name: '회원탈퇴' }));
    await userEvent.click(screen.getByRole('button', { name: '네' }));

    await waitFor(() => expect(withdraw).toHaveBeenCalledWith());
    expect(clearDraft).toHaveBeenCalledWith(7);
    expect(alertSpy).toHaveBeenCalledWith('회원탈퇴가 완료되었습니다.');
    expect(await screen.findByRole('heading', { name: '메인 화면' })).toBeInTheDocument();
  });
});

import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useAuth } from '../../features/auth/AuthProvider';
import { useCoverLetters } from '../../features/cover-letter/queries';
import type { CoverLetterSummary } from '../../features/cover-letter/types';
import { glideToElement } from '../../utils/glideScroll';
import { CoverLetterListPage } from './CoverLetterListPage';

vi.mock('../../features/auth/AuthProvider', () => ({ useAuth: vi.fn() }));
vi.mock('../../features/cover-letter/queries', () => ({ useCoverLetters: vi.fn() }));
vi.mock('../../utils/glideScroll', () => ({ glideToElement: vi.fn() }));

const letter = (id: number, title: string): CoverLetterSummary => ({
  id,
  title,
  targetCompany: '삼성전자',
  targetPosition: null,
  itemCount: 1,
  updatedAt: '2026-09-21T00:00:00Z',
});

function renderPage(letters: CoverLetterSummary[]) {
  vi.mocked(useAuth).mockReturnValue({ user: { id: 1 }, loading: false } as never);
  vi.mocked(useCoverLetters).mockReturnValue({
    state: { status: 'success', data: letters },
    retry: vi.fn(),
  } as never);
  return render(
    <MemoryRouter>
      <CoverLetterListPage />
    </MemoryRouter>,
  );
}

describe('CoverLetterListPage', () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it('첫 화면에는 자소서를 늘어놓지 않고 목록으로 내려가는 길만 둔다', async () => {
    renderPage([letter(1, '자소서1'), letter(2, '자소서2')]);

    // 첫 화면(목록 구획 바깥)에는 자소서 제목이 없다
    const saved = screen.getByRole('region', { name: '내 자기소개서' });
    expect(within(saved).getByText('자소서1')).toBeInTheDocument();
    expect(screen.getAllByText('자소서1')).toHaveLength(1);

    const goDown = screen.getByRole('button', { name: /내 자소서 보러가기/ });
    await userEvent.click(goDown);
    expect(vi.mocked(glideToElement)).toHaveBeenCalledWith('my-cover-letters', 106);
  });

  it('저장된 자소서가 없으면 내려가는 길 대신 안내를 보여 준다', () => {
    renderPage([]);

    expect(screen.queryByRole('button', { name: /내 자소서 보러가기/ })).not.toBeInTheDocument();
    expect(screen.getByText(/아직 저장된 자소서가 없습니다/)).toBeInTheDocument();
  });

  it('첫 화면 설명은 작성 중인 자소서를 올리라고 말한다', () => {
    renderPage([]);

    expect(screen.getByText(/작성 중인 자소서를 올리면/)).toBeInTheDocument();
  });
});

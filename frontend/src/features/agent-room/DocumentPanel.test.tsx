import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { DocumentPanel } from './DocumentPanel';
import type { CoverLetter } from '../cover-letter/types';

const { mockUpdate } = vi.hoisted(() => ({ mockUpdate: vi.fn() }));

vi.mock('../cover-letter/api', () => ({
  updateCoverLetter: mockUpdate,
}));

const letter: CoverLetter = {
  id: 33,
  title: '영풍 신입 지원',
  targetCompany: '영풍',
  targetPosition: 'SAP ERP',
  jobContextId: null,
  updatedAt: '2026-09-21',
  items: [{ id: 101, question: '지원 동기', answer: '앞 문장 바꿀 부분 뒤 문장', charLimit: 500 }],
};

describe('DocumentPanel 선택 수정', () => {
  it('드래그한 답변 일부만 교체해 저장한다', async () => {
    mockUpdate.mockResolvedValue(letter);
    const retry = vi.fn();
    render(
      <MemoryRouter>
        <DocumentPanel
          state={{ status: 'success', data: letter }}
          retry={retry}
          selectedItemId={letter.items[0].id}
          onReviewItem={vi.fn()}
          reviewingItemId={null}
          reviewBusy={false}
          reviewError={null}
        />
      </MemoryRouter>,
    );

    const answer = screen.getByText(letter.items[0].answer);
    const text = answer.firstChild;
    if (!text) throw new Error('답변 텍스트를 찾지 못했습니다.');

    const selected = '바꿀 부분';
    const start = letter.items[0].answer.indexOf(selected);
    const range = document.createRange();
    range.setStart(text, start);
    range.setEnd(text, start + selected.length);
    Object.defineProperty(range, 'getBoundingClientRect', {
      value: () => ({ left: 100, right: 180, top: 100, bottom: 120, width: 80, height: 20 }),
    });
    const browserSelection = window.getSelection();
    browserSelection?.removeAllRanges();
    browserSelection?.addRange(range);

    fireEvent.pointerUp(answer);

    const editor = await screen.findByRole('textbox', { name: '선택한 부분의 수정 내용' });
    const user = userEvent.setup();
    await user.clear(editor);
    await user.type(editor, '고친 부분');
    await user.click(screen.getByRole('button', { name: '적용' }));

    await waitFor(() => expect(mockUpdate).toHaveBeenCalledTimes(1));
    expect(mockUpdate.mock.calls[0][1].items[0].answer).toBe('앞 문장 고친 부분 뒤 문장');
    expect(retry).toHaveBeenCalled();
  });

  it('문항 버튼을 가로로 보여 주고 선택한 문항 하나만 펼친다', async () => {
    const onReviewItem = vi.fn();
    const multiple: CoverLetter = {
      ...letter,
      items: [
        letter.items[0],
        { id: 202, question: '입사 후 포부', answer: '성장하겠습니다.', charLimit: 500 },
      ],
    };

    render(
      <MemoryRouter>
        <DocumentPanel
          state={{ status: 'success', data: multiple }}
          retry={vi.fn()}
          selectedItemId={null}
          onReviewItem={onReviewItem}
          reviewingItemId={null}
          reviewBusy={false}
          reviewError={null}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole('button', { name: '문항 1' })).toHaveAttribute('aria-current', 'step');
    expect(screen.getByText('앞 문장 바꿀 부분 뒤 문장')).toBeInTheDocument();
    expect(screen.queryByText('성장하겠습니다.')).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: '문항 2' }));

    expect(screen.getByRole('button', { name: '문항 2' })).toHaveAttribute('aria-current', 'step');
    expect(screen.queryByText('앞 문장 바꿀 부분 뒤 문장')).not.toBeInTheDocument();
    expect(screen.getByText('성장하겠습니다.')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: '글쓰기 검토' }));

    expect(onReviewItem).toHaveBeenCalledWith(202);
  });

  it('검토 요청 중에는 문항 버튼을 잠그고 상태를 표시한다', () => {
    render(
      <MemoryRouter>
        <DocumentPanel
          state={{ status: 'success', data: letter }}
          retry={vi.fn()}
          selectedItemId={101}
          onReviewItem={vi.fn()}
          reviewingItemId={101}
          reviewBusy
          reviewError={null}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole('button', { name: '검토 요청 중…' })).toBeDisabled();
  });
});

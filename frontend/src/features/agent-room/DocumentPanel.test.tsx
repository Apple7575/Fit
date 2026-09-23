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
          onSelectItem={vi.fn()}
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

  it('여러 문항 중 검토할 문항을 선택한다', async () => {
    const onSelectItem = vi.fn();
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
          onSelectItem={onSelectItem}
        />
      </MemoryRouter>,
    );

    const buttons = screen.getAllByRole('button', { name: '이 문항 검토' });
    await userEvent.click(buttons[1]);

    expect(onSelectItem).toHaveBeenCalledWith(202);
  });
});

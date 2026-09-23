import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { MessageComposer } from './MessageComposer';

const { mockSendMessage } = vi.hoisted(() => ({ mockSendMessage: vi.fn() }));

vi.mock('./api', () => ({
  sendMessage: mockSendMessage,
}));

describe('MessageComposer 문항 선택', () => {
  it('선택한 문항 id를 발화 요청에 함께 보낸다', async () => {
    mockSendMessage.mockResolvedValue({ turnId: 77 });
    const onStarted = vi.fn();
    render(
      <MessageComposer
        roomId={3}
        coverLetterItemId={202}
        needsItemSelection={false}
        busy={false}
        onStarted={onStarted}
      />,
    );

    await userEvent.type(screen.getByRole('textbox', { name: '에이전트에게 할 말' }), '문장을 봐 주세요');
    await userEvent.click(screen.getByRole('button', { name: '보내기' }));

    expect(mockSendMessage).toHaveBeenCalledWith(3, '문장을 봐 주세요', 202);
    expect(onStarted).toHaveBeenCalledWith(77);
    expect(screen.queryByText(/중심으로 검토합니다/)).not.toBeInTheDocument();
  });

  it('여러 문항인데 선택하지 않으면 글쓰기 담당 안내를 보여 준다', () => {
    render(
      <MessageComposer
        roomId={3}
        coverLetterItemId={null}
        needsItemSelection
        busy={false}
        onStarted={vi.fn()}
      />,
    );

    expect(screen.getByText(/왼쪽에서 문항 하나를 선택/)).toBeInTheDocument();
  });
});

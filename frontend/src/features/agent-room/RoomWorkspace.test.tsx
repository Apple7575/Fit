import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { RoomWorkspace } from './RoomWorkspace';

const mocks = vi.hoisted(() => ({
  sendMessage: vi.fn(),
  reloadMessages: vi.fn(),
}));

vi.mock('./api', () => ({
  sendMessage: mocks.sendMessage,
}));

vi.mock('./queries', () => ({
  useRoom: () => ({
    state: {
      status: 'success',
      data: {
        roomId: 7,
        title: '글쓰기 검토',
        coverLetter: { id: 33, title: '영풍 신입 지원' },
        jobContext: null,
        agents: [{ agentKey: 'writing', name: '글쓰기 담당', auto: false, ready: true, config: {} }],
        createdAt: '2026-09-23T00:00:00',
        lastMessageAt: null,
      },
    },
    retry: vi.fn(),
  }),
}));

vi.mock('../cover-letter/queries', () => ({
  useOptionalCoverLetter: () => ({
    state: {
      status: 'success',
      data: {
        id: 33,
        title: '영풍 신입 지원',
        targetCompany: '영풍',
        targetPosition: 'SAP ERP',
        jobContextId: null,
        updatedAt: '2026-09-23',
        items: [
          { id: 101, question: '지원 동기', answer: '지원 동기 답변', charLimit: 500 },
          { id: 202, question: '입사 후 포부', answer: '입사 후 포부 답변', charLimit: 500 },
        ],
      },
    },
    retry: vi.fn(),
  }),
}));

vi.mock('./useLiveMessages', () => ({
  useLiveMessages: () => ({
    state: { status: 'success', data: { messages: [], nextCursor: null } },
    reload: mocks.reloadMessages,
  }),
}));

vi.mock('./useTurnPolling', () => ({
  useTurnPolling: () => null,
}));

vi.mock('./DocumentPanel', () => ({
  DocumentPanel: ({ onReviewItem }: { onReviewItem: (itemId: number) => void }) => (
    <button type="button" onClick={() => onReviewItem(202)}>
      두 번째 문항 검토
    </button>
  ),
}));

vi.mock('./MessageThread', () => ({ MessageThread: () => null }));
vi.mock('./MessageComposer', () => ({ MessageComposer: () => null }));

describe('RoomWorkspace 문항 즉시 검토', () => {
  it('문항 검토 버튼을 누르면 별도 입력 없이 해당 문항으로 턴을 시작한다', async () => {
    HTMLElement.prototype.scrollTo = vi.fn();
    mocks.sendMessage.mockResolvedValue({ turnId: 91, messageId: 92, status: 'PENDING', agents: [] });

    render(
      <MemoryRouter>
        <RoomWorkspace roomId={7} />
      </MemoryRouter>,
    );

    await userEvent.click(screen.getByRole('button', { name: '두 번째 문항 검토' }));

    await waitFor(() => {
      expect(mocks.sendMessage).toHaveBeenCalledWith(
        7,
        '선택한 자기소개서 문항을 글쓰기 담당 관점에서 검토해 주세요.',
        202,
        true,
      );
    });
  });
});

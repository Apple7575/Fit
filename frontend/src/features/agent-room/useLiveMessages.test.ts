import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchMessages } from './api';
import { useLiveMessages } from './useLiveMessages';
import type { MessagePage, RoomMessage } from './types';

vi.mock('./api', () => ({ fetchMessages: vi.fn() }));

const answered: RoomMessage = {
  messageId: 101,
  turnId: 100,
  role: 'agent',
  agentKey: 'writing',
  agentName: '글쓰기 담당',
  content: '결론이 뒤에 묻혀 있습니다.',
  evidences: [],
  basedOn: [],
  status: 'DONE',
  error: null,
  createdAt: '2026-09-14T10:00:00+09:00',
};

/** 서버는 최신순으로 준다. 맨 앞이 에이전트 답변이면 더 기다릴 것이 없는 대화다. */
const settledPage: MessagePage = { messages: [answered], nextCursor: null };

describe('useLiveMessages', () => {
  beforeEach(() => {
    vi.mocked(fetchMessages).mockReset();
  });

  it('다시 읽는 동안에도 보던 대화를 지우지 않는다', async () => {
    // 말을 걸면 곧바로 reload 가 불린다. 그때 로딩으로 되돌아가면 방금 쓴 말을 보여 주기는커녕
    // 있던 대화까지 한 왕복 동안 사라진다.
    vi.mocked(fetchMessages).mockResolvedValue(settledPage);

    const { result } = renderHook(() => useLiveMessages(7));
    await waitFor(() => expect(result.current.state.status).toBe('success'));

    let pending: (value: MessagePage) => void = () => {};
    vi.mocked(fetchMessages).mockReturnValue(
      new Promise<MessagePage>((resolve) => {
        pending = resolve;
      }),
    );

    act(() => result.current.reload());

    // 다음 응답이 오기 전까지도 대화는 그대로다
    expect(result.current.state.status).toBe('success');

    await act(async () => {
      pending(settledPage);
    });
    expect(result.current.state.status).toBe('success');
  });

  it('다른 방으로 옮기면 앞 방의 대화를 버린다', async () => {
    vi.mocked(fetchMessages).mockResolvedValue(settledPage);

    const { result, rerender } = renderHook(({ roomId }) => useLiveMessages(roomId), {
      initialProps: { roomId: 7 },
    });
    await waitFor(() => expect(result.current.state.status).toBe('success'));

    vi.mocked(fetchMessages).mockReturnValue(new Promise<MessagePage>(() => {}));
    rerender({ roomId: 8 });

    // 남의 방 대화를 잠깐이라도 보여 주면 안 된다
    expect(result.current.state.status).toBe('loading');
  });
});

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ThreadSidebar } from './ThreadSidebar';
import type { RoomSummary } from './types';

const room = (overrides: Partial<RoomSummary> = {}): RoomSummary => ({
  roomId: 1,
  title: '글쓰기 담당',
  agentCount: 1,
  lastMessagePreview: null,
  lastMessageAt: null,
  running: false,
  ready: true,
  need: null,
  ...overrides,
});

const sleeping = room({
  title: '기업 RAG 담당',
  ready: false,
  need: '지원 회사를 먼저 골라 주세요.',
});

describe('ThreadSidebar', () => {
  it('답할 수 있는 방은 마지막 대화를 그대로 보여 준다', () => {
    render(<ThreadSidebar rooms={[room()]} selectedRoomId={null} onSelect={vi.fn()} />);

    expect(screen.getByRole('button', { name: /글쓰기 담당/ })).toHaveAttribute(
      'title',
      '아직 대화 없음',
    );
  });

  it('답할 수 없는 방에는 사유를 글로 남긴다 — 흐린 색은 읽어 주는 화면에 닿지 않는다', () => {
    render(<ThreadSidebar rooms={[sleeping]} selectedRoomId={null} onSelect={vi.fn()} />);

    const chip = screen.getByRole('button', { name: /기업 RAG 담당/ });
    expect(chip).toHaveTextContent('지원 회사를 먼저 골라 주세요.');
    // 우리가 그린 말풍선을 쓰므로 브라우저 기본 설명은 달지 않는다
    expect(chip).not.toHaveAttribute('title');
  });

  it('마우스를 올리면 사유가 말풍선으로 뜨고, 치우면 사라진다', async () => {
    const user = userEvent.setup();
    render(<ThreadSidebar rooms={[sleeping]} selectedRoomId={null} onSelect={vi.fn()} />);

    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();

    await user.hover(screen.getByRole('button', { name: /기업 RAG 담당/ }));
    expect(await screen.findByRole('tooltip')).toHaveTextContent('지원 회사를 먼저 골라 주세요.');

    await user.unhover(screen.getByRole('button', { name: /기업 RAG 담당/ }));
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  it('답할 수 있는 방에는 말풍선을 띄우지 않는다', async () => {
    const user = userEvent.setup();
    render(<ThreadSidebar rooms={[room()]} selectedRoomId={null} onSelect={vi.fn()} />);

    await user.hover(screen.getByRole('button', { name: /글쓰기 담당/ }));

    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  it('사유가 없어도 답할 수 없다는 것은 말한다', async () => {
    const user = userEvent.setup();
    render(
      <ThreadSidebar
        onSelect={vi.fn()}
        rooms={[room({ ready: false, need: null })]}
        selectedRoomId={null}
      />,
    );

    await user.hover(screen.getByRole('button', { name: /글쓰기 담당/ }));

    expect(await screen.findByRole('tooltip')).toHaveTextContent('지금은 답할 수 없어요');
  });
});

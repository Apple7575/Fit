import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MessageThread } from './MessageThread';
import type { RoomMessage, TurnStatus } from './types';

const base: Pick<RoomMessage, 'turnId' | 'evidences' | 'basedOn' | 'error' | 'createdAt'> = {
  turnId: 100,
  evidences: [],
  basedOn: [],
  error: null,
  createdAt: '2026-09-14T10:00:00+09:00',
};

const userMessage: RoomMessage = {
  ...base,
  messageId: 100,
  role: 'user',
  agentKey: null,
  agentName: null,
  content: '2번 문항 봐줘',
  status: 'DONE',
};

const writingMessage: RoomMessage = {
  ...base,
  messageId: 101,
  role: 'agent',
  agentKey: 'writing',
  agentName: '글쓰기 담당',
  content: '결론이 뒤에 묻혀 있습니다.',
  status: 'DONE',
};

const names = { writing: '글쓰기 담당', news: '뉴스/트렌드 담당', supervisor: '총괄' };

describe('MessageThread', () => {
  beforeEach(() => {
    // jsdom 에는 scrollIntoView 가 없다. 칩이 부르는 것만 확인한다.
    Element.prototype.scrollIntoView = vi.fn();
  });

  it('대화가 없으면 무엇을 하라고 알려준다', () => {
    render(<MessageThread messages={[]} running={null} agentNames={names} />);

    expect(screen.getByText(/아직 대화가 없습니다/)).toBeInTheDocument();
  });

  it('사용자 발화와 에이전트 답변을 함께 보여준다', () => {
    render(
      <MessageThread messages={[userMessage, writingMessage]} running={null} agentNames={names} />,
    );

    expect(screen.getByText('2번 문항 봐줘')).toBeInTheDocument();
    expect(screen.getByText('결론이 뒤에 묻혀 있습니다.')).toBeInTheDocument();
    expect(screen.getByText('글쓰기 담당')).toBeInTheDocument();
  });

  it('실패한 에이전트는 목록에서 빠지지 않고 사유가 보인다', () => {
    const failed: RoomMessage = {
      ...base,
      messageId: 102,
      role: 'agent',
      agentKey: 'news',
      agentName: '뉴스/트렌드 담당',
      content: null,
      status: 'FAILED',
      error: '뉴스/트렌드 담당 가 볼 자료가 아직 준비되지 않았습니다.',
    };

    render(<MessageThread messages={[failed]} running={null} agentNames={names} />);

    expect(screen.getByText(/자료가 아직 준비되지 않았습니다/)).toBeInTheDocument();
  });

  it('아직 답하지 않은 에이전트는 자리만 먼저 보여준다', () => {
    const running: TurnStatus = {
      turnId: 100,
      status: 'RUNNING',
      agents: [
        { agentKey: 'writing', status: 'DONE', messageId: 101, error: null },
        { agentKey: 'news', status: 'RUNNING', messageId: null, error: null },
      ],
      supervisor: { agentKey: 'supervisor', status: 'PENDING', messageId: null, error: null },
    };

    render(<MessageThread messages={[writingMessage]} running={running} agentNames={names} />);

    expect(screen.getByText('살펴보는 중…')).toBeInTheDocument();
    expect(screen.getByText('차례를 기다리는 중…')).toBeInTheDocument();
    // 이미 답한 에이전트는 대기 자리로 또 나오지 않는다
    expect(screen.getAllByText('글쓰기 담당')).toHaveLength(1);
  });

  it('지난 턴에 답한 에이전트라도 이번 턴에서는 다시 기다리는 자리가 보인다', () => {
    // 턴을 가리지 않고 "답한 에이전트" 를 모으면, 지난 턴의 답변 때문에 이번 턴의 대기 자리가
    // 통째로 사라진다. 두 번째 말부터 기다리는 동안 화면이 멈춘 것처럼 보이던 문제다.
    const running: TurnStatus = {
      turnId: 200,
      status: 'RUNNING',
      agents: [{ agentKey: 'writing', status: 'PENDING', messageId: null, error: null }],
      supervisor: null,
    };
    const justAsked: RoomMessage = {
      ...base,
      turnId: 200,
      messageId: 200,
      role: 'user',
      agentKey: null,
      agentName: null,
      content: '이번엔 3번 문항 봐줘',
      status: 'DONE',
    };

    render(
      <MessageThread
        agentNames={names}
        messages={[userMessage, writingMessage, justAsked]}
        running={running}
      />,
    );

    expect(screen.getByText('이번엔 3번 문항 봐줘')).toBeInTheDocument();
    expect(screen.getByText('차례를 기다리는 중…')).toBeInTheDocument();
  });

  const supervisor: RoomMessage = {
    ...base,
    messageId: 103,
    role: 'agent',
    agentKey: 'supervisor',
    agentName: '총괄',
    content: '두괄식으로 올리고 기술 서술을 붙이세요.',
    basedOn: [101],
    status: 'DONE',
  };

  it('총괄 밑에 근거로 쓴 에이전트 칩이 붙는다', () => {
    render(
      <MessageThread messages={[writingMessage, supervisor]} running={null} agentNames={names} />,
    );

    expect(screen.getByText('근거')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /글쓰기 담당/ })).toBeInTheDocument();
  });

  it('근거 칩을 누르면 그 메시지로 이동한다', async () => {
    render(
      <MessageThread messages={[writingMessage, supervisor]} running={null} agentNames={names} />,
    );

    await userEvent.click(screen.getByRole('button', { name: /글쓰기 담당/ }));

    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
  });

  it('근거로 쓴 메시지가 화면에 없으면 칩을 띄우지 않는다', () => {
    render(<MessageThread messages={[supervisor]} running={null} agentNames={names} />);

    expect(screen.queryByText('근거')).not.toBeInTheDocument();
  });

  it('자동 검토 턴은 사용자 말풍선 대신 어디서 나온 답인지 알려준다', () => {
    const autoRoot: RoomMessage = {
      ...base,
      messageId: 200,
      role: 'user',
      agentKey: null,
      agentName: null,
      content: null,
      status: 'DONE',
    };

    render(
      <MessageThread messages={[autoRoot, writingMessage]} running={null} agentNames={names} />,
    );

    expect(screen.getByText('자소서를 받아 먼저 검토했습니다')).toBeInTheDocument();
    expect(screen.getByText('결론이 뒤에 묻혀 있습니다.')).toBeInTheDocument();
  });

  it('아직 답하지 않은 에이전트 자리가 대화에 있으면 기다리는 중으로 보인다', () => {
    const pending: RoomMessage = {
      ...base,
      messageId: 201,
      role: 'agent',
      agentKey: 'news',
      agentName: '뉴스/트렌드 담당',
      content: null,
      status: 'RUNNING',
    };

    render(<MessageThread messages={[pending]} running={null} agentNames={names} />);

    expect(screen.getByText('살펴보는 중…')).toBeInTheDocument();
  });

  it('총괄은 한 명의 의견이 아니라 종합이라는 것이 드러난다', () => {
    render(<MessageThread messages={[supervisor]} running={null} agentNames={names} />);

    expect(screen.getByText('종합')).toBeInTheDocument();
  });

  it('담당마다 이름표 색이 다르다 — 누가 한 말인지 눈으로 갈린다', () => {
    const news: RoomMessage = {
      ...base,
      messageId: 202,
      role: 'agent',
      agentKey: 'news',
      agentName: '뉴스/트렌드 담당',
      content: '최근 이슈를 얹어 보세요.',
      status: 'DONE',
    };

    render(<MessageThread messages={[writingMessage, news]} running={null} agentNames={names} />);

    const writingName = screen.getByText('글쓰기 담당');
    const newsName = screen.getByText('뉴스/트렌드 담당');
    expect(writingName.getAttribute('style')).not.toEqual(newsName.getAttribute('style'));
  });
});

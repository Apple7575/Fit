import { CharacterSlot } from '../../components/brand/CharacterSlot';
import { characterForAgent } from '../../components/brand/characters';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { isNotFound } from '../../api/client';
import { MessageComposer } from './MessageComposer';
import { MessageThread } from './MessageThread';
import { useRoom } from './queries';
import { useLiveMessages } from './useLiveMessages';
import { useTurnPolling } from './useTurnPolling';
import type { RoomAgent } from './types';

/** 칩에 설정 요약을 한 줄로 적는다. 방에 들어오자마자 무엇을 보고 말하는지 알 수 있게. */
function summarize(agent: RoomAgent): string | null {
  if (agent.config.companies?.length) {
    return agent.config.companies.map((company) => company.name ?? company.corpCode).join(', ');
  }
  if (agent.config.jobRole) return agent.config.jobRole;
  return null;
}

interface RoomWorkspaceProps {
  roomId: number;
  /** 대화가 끝나 사이드바의 미리보기가 바뀌었을 때 알린다. */
  onConversationChanged?: () => void;
}

/** 검토 방 한 개. 참여 에이전트와 대화. */
export function RoomWorkspace({ roomId, onConversationChanged }: RoomWorkspaceProps) {
  const { state: room, retry: reloadRoom } = useRoom(roomId);
  const { state: messages, reload: reloadMessages } = useLiveMessages(roomId);
  const [activeTurnId, setActiveTurnId] = useState<number | null>(null);

  const turn = useTurnPolling(roomId, activeTurnId, () => {
    setActiveTurnId(null);
    reloadMessages();
    // 마지막 대화 시각이 바뀌므로 방과 사이드바도 다시 읽는다.
    reloadRoom();
    onConversationChanged?.();
  });

  if (room.status === 'loading') {
    return (
      <p role="status" className="text-[14px] text-slate-400">
        불러오는 중…
      </p>
    );
  }
  if (room.status === 'error') {
    // 없거나 접근 불가한 방(404 ROOM_NOT_FOUND)은 재시도해도 같은 404 → 목록으로 유도한다.
    if (isNotFound(room.error)) {
      return (
        <div role="alert" className="rounded-xl border border-slate-200 bg-slate-50 p-4">
          <p className="text-[14px] font-medium text-slate-700">검토 방을 찾을 수 없습니다.</p>
          <Link
            to="/agent-rooms"
            className="mt-2 inline-block text-[13px] font-semibold text-blue-600 underline"
          >
            검토 방 목록으로
          </Link>
        </div>
      );
    }
    return (
      <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4">
        <p className="text-[14px] font-medium text-red-700">{room.error.message}</p>
        <button
          type="button"
          onClick={reloadRoom}
          className="mt-2 text-[13px] font-semibold text-red-700 underline"
        >
          다시 시도
        </button>
      </div>
    );
  }

  const data = room.data;
  const agentNames = Object.fromEntries(data.agents.map((agent) => [agent.agentKey, agent.name]));

  // 서버는 최신순으로 주는데 화면은 위에서 아래로 읽는다.
  const thread = messages.status === 'success' ? [...messages.data.messages].reverse() : [];
  // 자동 검토가 도는 중일 수도 있다. 그때 말을 걸면 서버가 409 로 막으므로 미리 잠근다.
  const busy =
    activeTurnId !== null ||
    thread.some((message) => message.status === 'PENDING' || message.status === 'RUNNING');

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h2 className="text-[18px] font-semibold text-slate-800">{data.title}</h2>
        <p className="mt-0.5 text-[13px] text-slate-500">
          {data.coverLetter ? data.coverLetter.title : '연결된 자소서 없음'}
          <span className="mx-1.5 text-slate-300">·</span>
          에이전트 {data.agents.length}명
          {data.jobContext && (
            <>
              <span className="mx-1.5 text-slate-300">·</span>
              공고 {data.jobContext.companyName} {data.jobContext.positionName}
            </>
          )}
        </p>
      </header>

      <ul aria-label="참여 에이전트" className="flex flex-wrap gap-1.5">
        {data.agents.map((agent) => {
          const summary = summarize(agent);
          return (
            <li
              key={agent.agentKey}
              className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1 text-[12px] text-slate-700"
            >
              <CharacterSlot
                character={characterForAgent(agent.agentKey)}
                interactive={false}
                size={18}
              />
              {agent.name}
              {summary && <span className="text-slate-500">· {summary}</span>}
              {agent.auto && <span className="text-[11px] text-slate-400">자동</span>}
              {!agent.ready && (
                <span className="text-[11px] font-medium text-amber-700">준비 안 됨</span>
              )}
            </li>
          );
        })}
      </ul>

      {messages.status === 'error' && (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3">
          <p className="text-[13px] font-medium text-red-700">{messages.error.message}</p>
          <button
            type="button"
            onClick={reloadMessages}
            className="mt-1 text-[12px] font-semibold text-red-700 underline"
          >
            다시 시도
          </button>
        </div>
      )}

      <MessageThread messages={thread} running={turn} agentNames={agentNames} />

      <MessageComposer
        roomId={roomId}
        busy={busy}
        onStarted={setActiveTurnId}
        onConflict={reloadMessages}
      />
    </div>
  );
}

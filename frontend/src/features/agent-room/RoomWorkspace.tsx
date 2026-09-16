import { CharacterSlot } from '../../components/brand/CharacterSlot';
import { characterForAgent } from '../../components/brand/characters';
import { useState } from 'react';
import { AgentConfigPanel } from './AgentConfigPanel';
import { MessageComposer } from './MessageComposer';
import { MessageThread } from './MessageThread';
import { useAgents, useJobRoles, useMessages, useRoom } from './queries';
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

/** 검토 방 한 개. 참여 에이전트, 설정, 그리고 대화. */
export function RoomWorkspace({ roomId, onConversationChanged }: RoomWorkspaceProps) {
  const { state: room, retry: reloadRoom } = useRoom(roomId);
  const { state: agents } = useAgents();
  const { state: jobRoles } = useJobRoles();
  const { state: messages, retry: reloadMessages } = useMessages(roomId);
  const [openAgentKey, setOpenAgentKey] = useState<string | null>(null);
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
  const open = data.agents.find((agent) => agent.agentKey === openAgentKey);
  const catalog = agents.status === 'success' ? agents.data : [];
  const roles = jobRoles.status === 'success' ? jobRoles.data : [];
  const agentNames = Object.fromEntries(data.agents.map((agent) => [agent.agentKey, agent.name]));

  // 서버는 최신순으로 주는데 화면은 위에서 아래로 읽는다.
  const thread = messages.status === 'success' ? [...messages.data.messages].reverse() : [];
  const busy = activeTurnId !== null;

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
          const selectable = !agent.auto;
          return (
            <li key={agent.agentKey}>
              <button
                type="button"
                disabled={!selectable || busy}
                aria-pressed={openAgentKey === agent.agentKey}
                onClick={() =>
                  setOpenAgentKey(openAgentKey === agent.agentKey ? null : agent.agentKey)
                }
                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[12px] transition ${
                  openAgentKey === agent.agentKey
                    ? 'border-blue-400 bg-blue-50 text-blue-800'
                    : 'border-slate-200 bg-white text-slate-700'
                } ${selectable && !busy ? 'hover:bg-slate-50' : 'cursor-default opacity-80'}`}
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
              </button>
            </li>
          );
        })}
      </ul>

      {open && (
        <AgentConfigPanel
          roomId={roomId}
          agent={open}
          catalog={catalog.find((entry) => entry.agentKey === open.agentKey)}
          jobRoles={roles}
          onSaved={() => {
            setOpenAgentKey(null);
            reloadRoom();
          }}
        />
      )}

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

      <MessageComposer roomId={roomId} busy={busy} onStarted={setActiveTurnId} />
    </div>
  );
}

import { useState } from 'react';
import { AgentConfigPanel } from './AgentConfigPanel';
import { useAgents, useJobRoles, useRoom } from './queries';
import type { RoomAgent } from './types';

/** 칩에 설정 요약을 한 줄로 적는다. 방에 들어오자마자 무엇을 보고 말하는지 알 수 있게. */
function summarize(agent: RoomAgent): string | null {
  if (agent.config.companies?.length) {
    return agent.config.companies.map((company) => company.name ?? company.corpCode).join(', ');
  }
  if (agent.config.jobRole) return agent.config.jobRole;
  if (agent.config.jdUrl) return '공고 연결됨';
  return null;
}

const DOT_COLORS: Record<string, string> = {
  jd: 'bg-blue-600',
  company: 'bg-violet-600',
  position: 'bg-emerald-600',
  news: 'bg-orange-600',
  writing: 'bg-slate-500',
  supervisor: 'bg-amber-600',
};

interface RoomWorkspaceProps {
  roomId: number;
}

/** 검토 방 한 개. 참여 에이전트 칩과 고른 에이전트의 설정 패널을 보여준다. */
export function RoomWorkspace({ roomId }: RoomWorkspaceProps) {
  const { state: room, retry: reloadRoom } = useRoom(roomId);
  const { state: agents } = useAgents();
  const { state: jobRoles } = useJobRoles();
  const [openAgentKey, setOpenAgentKey] = useState<string | null>(null);

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

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h2 className="text-[18px] font-semibold text-slate-800">{data.title}</h2>
        <p className="mt-0.5 text-[13px] text-slate-500">
          {data.coverLetter ? data.coverLetter.title : '연결된 자소서 없음'}
          <span className="mx-1.5 text-slate-300">·</span>
          에이전트 {data.agents.length}명
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
                disabled={!selectable}
                aria-pressed={openAgentKey === agent.agentKey}
                onClick={() =>
                  setOpenAgentKey(openAgentKey === agent.agentKey ? null : agent.agentKey)
                }
                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[12px] transition ${
                  openAgentKey === agent.agentKey
                    ? 'border-blue-400 bg-blue-50 text-blue-800'
                    : 'border-slate-200 bg-white text-slate-700'
                } ${selectable ? 'hover:bg-slate-50' : 'cursor-default opacity-80'}`}
              >
                <span
                  aria-hidden
                  className={`size-[7px] rounded-full ${DOT_COLORS[agent.agentKey] ?? 'bg-slate-400'}`}
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

      <p className="text-[12px] text-slate-400">
        대화는 다음 작업에서 붙입니다. 지금은 방을 만들고 에이전트가 볼 대상을 정하는 것까지 됩니다.
      </p>
    </div>
  );
}

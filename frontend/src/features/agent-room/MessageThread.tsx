import { AGENT_DOT } from './agentStyle';
import type { RoomMessage, TurnStatus } from './types';

interface MessageThreadProps {
  messages: RoomMessage[];
  /** 도는 중인 턴. 아직 답하지 않은 에이전트를 자리만 먼저 보여준다. */
  running: TurnStatus | null;
  agentNames: Record<string, string>;
}

/** 대화 한 줄. 사용자 발화는 오른쪽, 에이전트는 왼쪽에 이름표와 함께 붙인다. */
function MessageRow({ message }: { message: RoomMessage }) {
  if (message.role === 'user') {
    return (
      <li className="flex justify-end">
        <div className="max-w-[78%] rounded-xl border border-slate-200 bg-white px-3 py-2.5">
          <p className="text-[13px] leading-relaxed whitespace-pre-wrap text-slate-800">
            {message.content}
          </p>
        </div>
      </li>
    );
  }

  const failed = message.status === 'FAILED';
  return (
    <li className="flex gap-2.5">
      <span
        aria-hidden
        className={`mt-1 size-[10px] shrink-0 rounded-full ${AGENT_DOT[message.agentKey ?? ''] ?? 'bg-slate-400'}`}
      />
      <div className="min-w-0 flex-1">
        <p className="mb-1 text-[12px] text-slate-500">{message.agentName ?? message.agentKey}</p>

        {failed ? (
          <p
            role="status"
            className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] leading-relaxed text-red-700"
          >
            {message.error ?? '답하지 못했습니다.'}
          </p>
        ) : (
          <p className="text-[13px] leading-relaxed whitespace-pre-wrap text-slate-800">
            {message.content}
          </p>
        )}

        {message.basedOn.length > 0 && (
          <p className="mt-1.5 text-[11px] text-slate-400">
            근거 메시지 {message.basedOn.length}건을 종합했습니다
          </p>
        )}
      </div>
    </li>
  );
}

/** 아직 답하지 않은 에이전트 자리. 누가 남았는지 보여야 사용자가 기다릴 수 있다. */
function PendingRow({
  agentKey,
  name,
  status,
}: {
  agentKey: string;
  name: string;
  status: string;
}) {
  return (
    <li className="flex gap-2.5">
      <span
        aria-hidden
        className={`mt-1 size-[10px] shrink-0 rounded-full opacity-40 ${AGENT_DOT[agentKey] ?? 'bg-slate-400'}`}
      />
      <div>
        <p className="mb-0.5 text-[12px] text-slate-500">{name}</p>
        <p className="text-[13px] text-slate-400">
          {status === 'RUNNING' ? '살펴보는 중…' : '차례를 기다리는 중…'}
        </p>
      </div>
    </li>
  );
}

export function MessageThread({ messages, running, agentNames }: MessageThreadProps) {
  const answered = new Set(
    messages.filter((message) => message.role === 'agent').map((message) => message.agentKey),
  );
  const waiting = (running?.agents ?? [])
    .concat(running?.supervisor ? [running.supervisor] : [])
    .filter((agent) => !answered.has(agent.agentKey) && agent.status !== 'DONE');

  if (messages.length === 0 && waiting.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-slate-200 px-4 py-8 text-center text-[13px] text-slate-400">
        아직 대화가 없습니다. 아래에 무엇을 봐 달라고 적어 보세요.
      </p>
    );
  }

  return (
    <ul aria-label="대화 내역" className="flex flex-col gap-4">
      {messages.map((message) => (
        <MessageRow key={message.messageId} message={message} />
      ))}
      {waiting.map((agent) => (
        <PendingRow
          key={agent.agentKey}
          agentKey={agent.agentKey}
          name={agentNames[agent.agentKey] ?? agent.agentKey}
          status={agent.status}
        />
      ))}
    </ul>
  );
}

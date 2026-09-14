import { useEffect, useRef, useState } from 'react';
import { AGENT_DOT } from './agentStyle';
import type { RoomMessage, TurnStatus } from './types';

interface MessageThreadProps {
  messages: RoomMessage[];
  /** 도는 중인 턴. 아직 답하지 않은 에이전트를 자리만 먼저 보여준다. */
  running: TurnStatus | null;
  agentNames: Record<string, string>;
}

const rowId = (messageId: number) => `room-message-${messageId}`;

/**
 * 총괄이 종합에 쓴 메시지로 이동하는 칩.
 *
 * <p>"무엇을 근거로 그렇게 말했나" 가 눌러서 확인되지 않으면 사용자는 총괄을 믿을 근거가
 * 없다. 근거로 쓰인 메시지가 화면에 없으면(이전 페이지) 칩도 띄우지 않는다.
 */
function BasedOnChips({
  basedOn,
  lookup,
  onJump,
}: {
  basedOn: number[];
  lookup: Map<number, RoomMessage>;
  onJump: (messageId: number) => void;
}) {
  const found = basedOn.map((id) => lookup.get(id)).filter((m): m is RoomMessage => m !== undefined);
  if (found.length === 0) {
    return null;
  }

  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5">
      <span className="text-[11px] text-slate-400">근거</span>
      {found.map((source) => (
        <button
          key={source.messageId}
          type="button"
          onClick={() => onJump(source.messageId)}
          className="inline-flex items-center gap-1 rounded-full border border-slate-200 px-2 py-0.5 text-[11px] text-slate-600 transition hover:border-slate-300 hover:bg-slate-50"
        >
          <span
            aria-hidden
            className={`size-[6px] rounded-full ${AGENT_DOT[source.agentKey ?? ''] ?? 'bg-slate-400'}`}
          />
          {source.agentName ?? source.agentKey}
        </button>
      ))}
    </div>
  );
}

function MessageRow({
  message,
  focused,
  lookup,
  onJump,
}: {
  message: RoomMessage;
  focused: boolean;
  lookup: Map<number, RoomMessage>;
  onJump: (messageId: number) => void;
}) {
  const ring = focused ? 'ring-2 ring-blue-300' : '';

  if (message.role === 'user') {
    return (
      <li id={rowId(message.messageId)} className="flex justify-end">
        <div className={`max-w-[78%] rounded-xl border border-slate-200 bg-white px-3 py-2.5 ${ring}`}>
          <p className="text-[13px] leading-relaxed whitespace-pre-wrap text-slate-800">
            {message.content}
          </p>
        </div>
      </li>
    );
  }

  const failed = message.status === 'FAILED';
  return (
    <li id={rowId(message.messageId)} className={`flex gap-2.5 rounded-lg ${ring}`}>
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

        <BasedOnChips basedOn={message.basedOn} lookup={lookup} onJump={onJump} />
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
  const [focusedId, setFocusedId] = useState<number | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => () => clearTimeout(timer.current), []);

  const jumpTo = (messageId: number) => {
    document.getElementById(rowId(messageId))?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    // 이동만 하면 어디로 갔는지 놓친다. 잠깐 테두리를 둘러 눈이 따라가게 한다.
    setFocusedId(messageId);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setFocusedId(null), 1600);
  };

  const lookup = new Map(messages.map((message) => [message.messageId, message]));
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
        <MessageRow
          key={message.messageId}
          message={message}
          focused={focusedId === message.messageId}
          lookup={lookup}
          onJump={jumpTo}
        />
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

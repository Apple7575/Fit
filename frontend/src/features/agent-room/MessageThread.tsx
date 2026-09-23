import { CharacterSlot } from '../../components/brand/CharacterSlot';
import { characterForAgent } from '../../components/brand/characters';
import { useEffect, useRef, useState } from 'react';
import { agentPalette } from './agentStyle';
import type { Evidence, RoomMessage, TurnStatus } from './types';

interface MessageThreadProps {
  messages: RoomMessage[];
  /** 도는 중인 턴. 아직 자리도 생기지 않은 에이전트를 먼저 보여준다. */
  running: TurnStatus | null;
  agentNames: Record<string, string>;
}

const rowId = (messageId: number) => `room-message-${messageId}`;

/** 자동 검토 턴의 뿌리. 사용자가 한 말이 아니므로 말풍선이 아니라 구분선으로 그린다. */
const isAutoReview = (message: RoomMessage) =>
  message.role === 'user' && (message.content === null || message.content.trim() === '');

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
  const found = basedOn
    .map((id) => lookup.get(id))
    .filter((m): m is RoomMessage => m !== undefined);
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
          <CharacterSlot
            character={characterForAgent(source.agentKey)}
            interactive={false}
            size={14}
          />
          {source.agentName ?? source.agentKey}
        </button>
      ))}
    </div>
  );
}

/** AI 가 주는 자료 종류를 사람이 읽는 말로. 모르는 값은 그대로 쓴다. */
const SOURCE_LABEL: Record<string, string> = {
  NEWS_ARTICLE: '뉴스',
  JOB_POSTING: '공고',
  USER_DOCUMENT: '자소서',
  COMPANY_REPORT: '공시',
};

const sourceLabel = (docType: string | null) =>
  docType ? (SOURCE_LABEL[docType.toUpperCase()] ?? docType) : '자료';

/**
 * 그 담당이 실제로 읽은 자료.
 *
 * <p>이 서비스의 코치는 성격이 아니라 자료로 나뉜다. 어느 문서 몇 년 자료에서 나온 말인지
 * 붙지 않으면 일반 챗봇과 구별되지 않는다. 눌러서 원문 조각까지 펼친다.
 */
function EvidenceList({ evidences }: { evidences: Evidence[] }) {
  const [open, setOpen] = useState<number | null>(null);
  if (evidences.length === 0) {
    return null;
  }
  const opened = open !== null ? evidences[open] : null;

  return (
    <div className="mt-2">
      <ul className="flex flex-wrap items-center gap-1.5">
        <li className="text-[11px] text-slate-400">읽은 자료</li>
        {evidences.map((evidence, i) => (
          <li key={i}>
            <button
              aria-expanded={open === i}
              className={`inline-flex max-w-[220px] items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] transition ${
                open === i
                  ? 'border-slate-400 bg-white text-slate-800'
                  : 'border-slate-200 text-slate-600 hover:border-slate-300 hover:bg-white'
              }`}
              onClick={() => setOpen(open === i ? null : i)}
              type="button"
            >
              <span className="shrink-0 font-semibold">{sourceLabel(evidence.docType)}</span>
              <span className="truncate">{evidence.title ?? '제목 없음'}</span>
              {evidence.year !== null && <span className="shrink-0 text-slate-400">{evidence.year}</span>}
            </button>
          </li>
        ))}
      </ul>
      {opened && (opened.snippet || opened.url) && (
        <div className="mt-1.5 rounded-xl border border-slate-200 bg-white p-2.5">
          {opened.snippet && (
            <p className="text-[12px] leading-5 break-keep wrap-anywhere whitespace-pre-wrap text-slate-600">
              {opened.snippet}
            </p>
          )}
          {/* 기사 근거는 원문으로 넘어갈 수 있어야 "무엇을 읽었나"가 끝까지 확인된다 */}
          {opened.url && (
            <a
              className={`inline-block text-[12px] font-semibold text-blue-600 hover:underline ${
                opened.snippet ? 'mt-1.5' : ''
              }`}
              href={opened.url}
              rel="noreferrer"
              target="_blank"
            >
              원문 보기 ↗
            </a>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * 말풍선 꼬리. 말한 사람 쪽으로 돌린 네모다.
 *
 * <p>바탕색이 불투명해야 말풍선과 겹치는 자리가 진해지지 않는다. 그래서 색은 투명도가 아니라
 * 흰색을 섞어 만든다(agentStyle).
 */
function Tail({ side, tint, line }: { side: 'left' | 'right'; tint: string; line: string }) {
  const place =
    side === 'left'
      ? 'left-[-5px] top-[16px] border-b border-l'
      : 'right-[-5px] top-[16px] border-t border-r';
  return (
    <span
      aria-hidden
      className={`absolute h-[10px] w-[10px] rotate-45 ${place}`}
      style={{ backgroundColor: tint, borderColor: line }}
    />
  );
}

/** 사용자가 직접 건 말. 오른쪽에 붙어 에이전트 쪽과 갈린다. */
function UserRow({ message, ring }: { message: RoomMessage; ring: string }) {
  return (
    <li id={rowId(message.messageId)} className="flex justify-end">
      <div
        className={`relative max-w-[78%] rounded-2xl border border-slate-200 bg-white px-3.5 py-2.5 ${ring}`}
      >
        <Tail side="right" tint="#ffffff" line="#e2e8f0" />
        <p className="text-[13px] leading-relaxed break-keep wrap-anywhere whitespace-pre-wrap text-slate-800">
          {message.content}
        </p>
      </div>
    </li>
  );
}

/**
 * 자소서를 받아 알아서 검토했다는 표시.
 *
 * <p>사용자가 하지 않은 말을 말풍선으로 지어내지 않는다. 대신 아래 답변들이 어디서 나온
 * 것인지는 알려 줘야 한다 — 묻지도 않았는데 답이 와 있으면 무엇을 본 것인지 모른다.
 */
function AutoReviewRow({ message }: { message: RoomMessage }) {
  return (
    <li id={rowId(message.messageId)} className="flex items-center gap-3 py-1">
      <span className="h-px flex-1 bg-slate-200" />
      <span className="shrink-0 text-[12px] text-slate-400">자소서를 받아 먼저 검토했습니다</span>
      <span className="h-px flex-1 bg-slate-200" />
    </li>
  );
}

/** 아직 답이 오지 않은 자리에 띄울 한 줄. */
const waitingText = (status: string) =>
  status === 'RUNNING' ? '살펴보는 중…' : '차례를 기다리는 중…';

function AgentRow({
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
  const palette = agentPalette(message.agentKey);
  const lead = message.agentKey === 'supervisor';
  const failed = message.status === 'FAILED';
  const waiting = message.status === 'PENDING' || message.status === 'RUNNING';

  return (
    <li
      id={rowId(message.messageId)}
      className={`flex gap-2.5 rounded-lg ${focused ? 'ring-2 ring-blue-300' : ''}`}
    >
      <span className={`mt-0.5 shrink-0 ${waiting ? 'opacity-50' : ''}`}>
        <CharacterSlot
          character={characterForAgent(message.agentKey)}
          mood={message.status === 'RUNNING' ? 'wow' : waiting ? 'sleepy' : 'neutral'}
          size={28}
        />
      </span>

      {/* 총괄은 다른 담당의 말을 모은 것이라 한 명의 의견처럼 좁게 두지 않는다. */}
      <div className={`min-w-0 ${lead ? 'flex-1' : 'max-w-[82%]'}`}>
        <p className="mb-1 flex items-center gap-1.5 text-[12px] font-medium">
          <span style={{ color: palette.ink }}>{message.agentName ?? message.agentKey}</span>
          {lead && (
            <span className="rounded-full bg-slate-100 px-1.5 py-px text-[10px] text-slate-500">
              종합
            </span>
          )}
        </p>

        {failed ? (
          <div className="relative rounded-2xl border border-red-200 bg-red-50 px-3.5 py-2.5">
            <Tail side="left" tint="#fef2f2" line="#fecaca" />
            <p role="status" className="text-[13px] leading-relaxed text-red-700">
              {message.error ?? '답하지 못했습니다.'}
            </p>
          </div>
        ) : (
          <div
            className="relative rounded-2xl border px-3.5 py-2.5"
            style={{ backgroundColor: palette.tint, borderColor: palette.line }}
          >
            <Tail side="left" tint={palette.tint} line={palette.line} />
            {waiting ? (
              <p role="status" className="text-[13px] text-slate-400">
                {waitingText(message.status)}
              </p>
            ) : (
              <p className="text-[13px] leading-relaxed break-keep wrap-anywhere whitespace-pre-wrap text-slate-800">
                {message.content}
              </p>
            )}
          </div>
        )}

        <EvidenceList evidences={message.evidences} />
        <BasedOnChips basedOn={message.basedOn} lookup={lookup} onJump={onJump} />
      </div>
    </li>
  );
}

/** 자리조차 아직 생기지 않은 에이전트. 누가 남았는지 보여야 사용자가 기다릴 수 있다. */
function PendingRow({
  agentKey,
  name,
  status,
}: {
  agentKey: string;
  name: string;
  status: string;
}) {
  const palette = agentPalette(agentKey);
  return (
    <li className="flex gap-2.5">
      <span className="mt-0.5 shrink-0 opacity-50">
        <CharacterSlot
          character={characterForAgent(agentKey)}
          mood={status === 'RUNNING' ? 'wow' : 'sleepy'}
          size={28}
        />
      </span>
      <div className="max-w-[82%] min-w-0">
        <p className="mb-1 text-[12px] font-medium" style={{ color: palette.ink }}>
          {name}
        </p>
        <div
          className="relative rounded-2xl border px-3.5 py-2.5"
          style={{ backgroundColor: palette.tint, borderColor: palette.line }}
        >
          <Tail side="left" tint={palette.tint} line={palette.line} />
          <p className="text-[13px] text-slate-400">{waitingText(status)}</p>
        </div>
      </div>
    </li>
  );
}

export function MessageThread({ messages, running, agentNames }: MessageThreadProps) {
  const [focusedId, setFocusedId] = useState<number | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => () => clearTimeout(timer.current), []);

  const jumpTo = (messageId: number) => {
    document
      .getElementById(rowId(messageId))
      ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    // 이동만 하면 어디로 갔는지 놓친다. 잠깐 테두리를 둘러 눈이 따라가게 한다.
    setFocusedId(messageId);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setFocusedId(null), 1600);
  };

  const lookup = new Map(messages.map((message) => [message.messageId, message]));
  /*
   * 이번 턴에 이미 자리가 생긴 담당. 자리가 있으면 그 줄이 스스로 상태를 보여 주므로
   * (AgentRow 가 PENDING·RUNNING 을 그린다) 대기 줄을 덧붙이지 않는다.
   *
   * <p>턴을 가리지 않고 모으면 지난 턴이나 자동 검토의 답변 때문에 모든 담당이 "답한 것" 이
   * 되어, 정작 이번 턴의 대기 줄이 통째로 사라진다. 두 번째 말부터는 기다리는 동안 화면이
   * 멈춘 것처럼 보였던 이유다.
   */
  const seatedThisTurn = new Set(
    messages
      .filter((message) => message.role === 'agent' && message.turnId === running?.turnId)
      .map((message) => message.agentKey),
  );
  const waiting = (running?.agents ?? [])
    .concat(running?.supervisor ? [running.supervisor] : [])
    .filter((agent) => !seatedThisTurn.has(agent.agentKey) && agent.status !== 'DONE');

  if (messages.length === 0 && waiting.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-slate-200 px-4 py-8 text-center text-[13px] text-slate-400">
        아직 대화가 없습니다. 아래에 무엇을 봐 달라고 적어 보세요.
      </p>
    );
  }

  return (
    <ul aria-label="대화 내역" className="flex flex-col gap-4">
      {messages.map((message) => {
        if (isAutoReview(message)) {
          return <AutoReviewRow key={message.messageId} message={message} />;
        }
        if (message.role === 'user') {
          return (
            <UserRow
              key={message.messageId}
              message={message}
              ring={focusedId === message.messageId ? 'ring-2 ring-blue-300' : ''}
            />
          );
        }
        return (
          <AgentRow
            key={message.messageId}
            message={message}
            focused={focusedId === message.messageId}
            lookup={lookup}
            onJump={jumpTo}
          />
        );
      })}
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

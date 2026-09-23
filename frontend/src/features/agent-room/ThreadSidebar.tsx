import { useState } from 'react';
import { CharacterSlot } from '../../components/brand/CharacterSlot';
import { characterForRoomTitle } from '../../components/brand/characters';
import type { RoomSummary } from './types';

interface ThreadSidebarProps {
  rooms: RoomSummary[];
  selectedRoomId: number | null;
  onSelect: (roomId: number) => void;
  /**
   * 자리가 넉넉한 곳(입장 화면)에서는 옆으로 밀지 않고 줄바꿈한다. 좁은 곳에서 가로로
   * 미는 것은 자리가 없어서지, 그게 더 나아서가 아니다.
   */
  wrap?: boolean;
}

/** 서버가 사유를 못 준 경우에도 답할 수 없다는 것은 말한다. */
const UNKNOWN_NEED = '지금은 답할 수 없어요';

/** 말풍선이 가리킬 자리. 화면 기준(fixed) 좌표다. */
interface Hint {
  roomId: number;
  text: string;
  x: number;
  y: number;
}

/** 에이전트 전담 방과 총괄 논의 방을 한 줄의 선택 버튼으로 보여준다. */
export function ThreadSidebar({ rooms, selectedRoomId, onSelect, wrap = false }: ThreadSidebarProps) {
  /*
   * 말풍선을 칩 안에 넣지 않고 화면 기준으로 띄운다. 칩 줄은 좁은 곳에서 가로로 미는
   * 스크롤 상자라(overflow-x-auto), 그 안에 절대 위치로 올린 말풍선은 상자 밖으로 나가지
   * 못하고 잘린다. 칩의 자리만 재서 화면 위에 띄우면 잘릴 곳이 없다.
   */
  const [hint, setHint] = useState<Hint | null>(null);

  // 총괄 논의를 맨 앞에 두고 이어서 개별 에이전트를 배치한다.
  const ordered = [...rooms].sort((a, b) => Number(b.agentCount > 1) - Number(a.agentCount > 1));

  const openHint = (room: RoomSummary, chip: HTMLElement) => {
    const box = chip.getBoundingClientRect();
    setHint({
      roomId: room.roomId,
      text: room.need ?? UNKNOWN_NEED,
      x: box.left + box.width / 2,
      y: box.top,
    });
  };

  const closeHint = (roomId: number) =>
    setHint((current) => (current?.roomId === roomId ? null : current));

  const row = (room: RoomSummary) => {
    const selected = room.roomId === selectedRoomId;
    const isGroup = room.agentCount > 1;
    /*
     * 지금 답할 수 없는 방은 칩에서 바로 알린다. 무엇을 채우면 되는지(need)는 서버가 준 문구를
     * 그대로 쓴다 — 보내고 나서 받는 400 과 같은 말이어야 사용자가 둘을 한 문제로 읽는다.
     *
     * 입력칸 위에 안내 상자를 두었더니 좁은 채팅 패널의 세로를 계속 먹었다. 담당이 이미 있는
     * 자리에 붙이면 자리를 더 쓰지 않는다.
     */
    const sleeping = !room.ready;
    return (
      <li key={room.roomId}>
        <button
          type="button"
          aria-current={selected ? 'true' : undefined}
          onClick={() => onSelect(room.roomId)}
          // 자는 칩은 우리가 그린 말풍선을 쓴다. title 까지 두면 설명이 둘 다 뜬다.
          title={sleeping ? undefined : (room.lastMessagePreview ?? '아직 대화 없음')}
          onMouseEnter={sleeping ? (event) => openHint(room, event.currentTarget) : undefined}
          onMouseLeave={sleeping ? () => closeHint(room.roomId) : undefined}
          onFocus={sleeping ? (event) => openHint(room, event.currentTarget) : undefined}
          onBlur={sleeping ? () => closeHint(room.roomId) : undefined}
          className={`flex h-9 max-w-44 items-center gap-1.5 rounded-full border px-2.5 text-left transition ${
            selected
              ? 'border-blue-200 bg-blue-50 text-blue-700'
              : sleeping
                ? 'border-dashed border-slate-300 bg-slate-50 text-slate-400 hover:border-slate-400 hover:text-slate-600'
                : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50'
          }`}
        >
          <span className={`relative shrink-0 ${sleeping ? 'opacity-60 grayscale' : ''}`}>
            <CharacterSlot
              character={isGroup ? 'lead' : characterForRoomTitle(room.title)}
              interactive={false}
              mood={sleeping ? 'sleepy' : 'neutral'}
              size={20}
            />
            {/* 흑백만으로는 "고장인지 자는 것인지" 를 알 수 없다. 자고 있다고 그림으로 말한다. */}
            {sleeping && <SleepMark />}
          </span>
          <span className="truncate text-[12px] font-semibold">
            {room.title}
          </span>
          {/* 흐린 색도 말풍선도 읽어 주는 화면에는 닿지 않는다. 사유를 글로도 남긴다. */}
          {sleeping && <span className="sr-only"> — {room.need ?? UNKNOWN_NEED}</span>}
          {room.running && (
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-blue-500" aria-label="답하는 중" />
          )}
        </button>
      </li>
    );
  };

  return (
    <>
      <nav
        aria-label="대화 목록"
        className={wrap ? undefined : 'overflow-x-auto pb-1'}
        // 칩을 옆으로 밀면 재어 둔 자리가 어긋난다. 그때는 말풍선을 거둔다.
        onScroll={hint ? () => setHint(null) : undefined}
      >
        <ul className={wrap ? 'flex flex-wrap justify-center gap-2' : 'flex min-w-max gap-2'}>
          {ordered.map(row)}
        </ul>
      </nav>

      {hint && <NeedBubble hint={hint} />}
    </>
  );
}

/** 자고 있다는 표시. 칩이 작아 글자 두 개로만 말한다. */
function SleepMark() {
  return (
    <span
      aria-hidden="true"
      className="absolute -top-1.5 -right-1 leading-none font-black tracking-tighter text-slate-400"
    >
      <span className="text-[9px]">z</span>
      <span className="text-[7px]">z</span>
    </span>
  );
}

/**
 * 칩 위에 뜨는 사유 말풍선.
 *
 * <p>화면 기준으로 띄워 스크롤 상자에 잘리지 않게 한다. 누르는 것을 가로막지 않도록
 * 이벤트는 통과시킨다.
 */
function NeedBubble({ hint }: { hint: Hint }) {
  return (
    <div
      role="tooltip"
      className="pointer-events-none fixed z-50 -translate-x-1/2 -translate-y-full pb-1.5"
      style={{ left: hint.x, top: hint.y }}
    >
      <div className="relative max-w-56 rounded-lg bg-slate-900 px-2.5 py-1.5 text-[11px] leading-snug font-medium break-keep text-white shadow-lg">
        {hint.text}
        <span
          aria-hidden="true"
          className="absolute top-full left-1/2 size-2 -translate-x-1/2 -translate-y-1/2 rotate-45 bg-slate-900"
        />
      </div>
    </div>
  );
}

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

/** 에이전트 전담 방과 총괄 논의 방을 한 줄의 선택 버튼으로 보여준다. */
export function ThreadSidebar({ rooms, selectedRoomId, onSelect, wrap = false }: ThreadSidebarProps) {
  // 총괄 논의를 맨 앞에 두고 이어서 개별 에이전트를 배치한다.
  const ordered = [...rooms].sort((a, b) => Number(b.agentCount > 1) - Number(a.agentCount > 1));

  const row = (room: RoomSummary) => {
    const selected = room.roomId === selectedRoomId;
    const isGroup = room.agentCount > 1;
    return (
      <li key={room.roomId}>
        <button
          type="button"
          aria-current={selected ? 'true' : undefined}
          onClick={() => onSelect(room.roomId)}
          title={room.lastMessagePreview ?? '아직 대화 없음'}
          className={`flex h-9 max-w-44 items-center gap-1.5 rounded-full border px-2.5 text-left transition ${
            selected
              ? 'border-blue-200 bg-blue-50 text-blue-700'
              : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50'
          }`}
        >
          <span className="shrink-0">
            <CharacterSlot
              character={isGroup ? 'lead' : characterForRoomTitle(room.title)}
              interactive={false}
              size={20}
            />
          </span>
          <span className="truncate text-[12px] font-semibold">
            {room.title}
          </span>
          {room.running && (
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-blue-500" aria-label="답하는 중" />
          )}
        </button>
      </li>
    );
  };

  return (
    <nav aria-label="대화 목록" className={wrap ? undefined : 'overflow-x-auto pb-1'}>
      <ul className={wrap ? 'flex flex-wrap justify-center gap-2' : 'flex min-w-max gap-2'}>
        {ordered.map(row)}
      </ul>
    </nav>
  );
}

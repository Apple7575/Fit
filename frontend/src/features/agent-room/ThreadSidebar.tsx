import { CharacterSlot } from '../../components/brand/CharacterSlot';
import { characterForRoomTitle } from '../../components/brand/characters';
import type { RoomSummary } from './types';

interface ThreadSidebarProps {
  rooms: RoomSummary[];
  selectedRoomId: number | null;
  onSelect: (roomId: number) => void;
  /** 넓은 화면에서 플로팅 패널 왼쪽에 붙는 세로 책갈피 모양. */
  bookmarks?: boolean;
}

/** 에이전트 전담 방과 총괄 논의 방을 한 줄의 선택 버튼으로 보여준다. */
export function ThreadSidebar({ rooms, selectedRoomId, onSelect, bookmarks = false }: ThreadSidebarProps) {
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
            bookmarks
              ? 'xl:h-11 xl:w-[132px] xl:max-w-none xl:rounded-l-xl xl:rounded-r-none xl:border-r-0 xl:px-3 xl:shadow-sm'
              : ''
          } ${
            selected
              ? bookmarks
                ? 'border-blue-200 bg-blue-50 text-blue-700 xl:border-blue-600 xl:bg-blue-600 xl:text-blue-50'
                : 'border-blue-200 bg-blue-50 text-blue-700'
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
    <nav
      aria-label="대화 목록"
      className={bookmarks ? 'overflow-x-auto pb-1 xl:overflow-visible xl:pb-0' : 'overflow-x-auto pb-1'}
    >
      <ul className={`flex min-w-max gap-2 ${bookmarks ? 'xl:flex-col xl:items-end xl:gap-1.5' : ''}`}>
        {ordered.map(row)}
      </ul>
    </nav>
  );
}

import { CharacterSlot } from '../../components/brand/CharacterSlot';
import { characterForRoomTitle } from '../../components/brand/characters';
import type { RoomSummary } from './types';

interface ThreadSidebarProps {
  rooms: RoomSummary[];
  selectedRoomId: number | null;
  onSelect: (roomId: number) => void;
}

/**
 * 왼쪽 스레드 목록. 에이전트 전담 방이 1:1 대화이고, 에이전트가 여럿인 방이 총괄 논의다.
 *
 * <p>메신저처럼 마지막 대화를 미리 보여준다. 무엇을 물어봤던 방인지 제목만으로는 모른다.
 */
export function ThreadSidebar({ rooms, selectedRoomId, onSelect }: ThreadSidebarProps) {
  const solo = rooms.filter((room) => room.agentCount <= 1);
  const group = rooms.filter((room) => room.agentCount > 1);

  const row = (room: RoomSummary) => {
    const selected = room.roomId === selectedRoomId;
    const isGroup = room.agentCount > 1;
    return (
      <li key={room.roomId}>
        <button
          type="button"
          aria-current={selected ? 'true' : undefined}
          onClick={() => onSelect(room.roomId)}
          className={`flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2 text-left transition ${
            selected ? 'bg-slate-100' : 'hover:bg-slate-50'
          }`}
        >
          <span className="mt-0.5 shrink-0">
            <CharacterSlot
              character={isGroup ? 'lead' : characterForRoomTitle(room.title)}
              interactive={false}
              size={24}
            />
          </span>
          <span className="min-w-0 flex-1">
            <span className="flex items-center gap-1.5">
              <span className="truncate text-[13px] font-semibold text-slate-800">
                {room.title}
              </span>
              {room.running && (
                <span className="shrink-0 text-[11px] font-medium text-blue-600">답하는 중</span>
              )}
            </span>
            <span className="block truncate text-[12px] text-slate-400">
              {room.lastMessagePreview ?? '아직 대화 없음'}
            </span>
          </span>
        </button>
      </li>
    );
  };

  return (
    <nav aria-label="대화 목록" className="flex flex-col gap-4">
      {group.length > 0 && (
        <div>
          <p className="mb-1 px-2.5 text-[11px] font-medium text-slate-400">함께 논의</p>
          <ul>{group.map(row)}</ul>
        </div>
      )}
      <div>
        <p className="mb-1 px-2.5 text-[11px] font-medium text-slate-400">에이전트</p>
        <ul>{solo.map(row)}</ul>
      </div>
    </nav>
  );
}

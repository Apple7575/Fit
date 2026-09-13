import { Navigate, useNavigate } from 'react-router-dom';
import { CoverLetterHeader } from '../cover-letter/CoverLetterHeader';
import { useAuth } from '../../features/auth/AuthProvider';
import { RoomCreateForm } from '../../features/agent-room/RoomCreateForm';
import { useRooms } from '../../features/agent-room/queries';

/** 검토 방 목록. 방을 고르거나 새로 만든다. */
export function AgentRoomListPage() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50">
        <CoverLetterHeader />
        <p className="mx-auto max-w-4xl px-6 py-16 text-center text-sm text-slate-400" role="status">
          불러오는 중…
        </p>
      </div>
    );
  }

  // 방은 저장되는 것이라 로그인해야 한다.
  if (!user) return <Navigate replace to="/login" />;

  return (
    <div className="min-h-screen bg-slate-50">
      <CoverLetterHeader />
      <ListBody />
    </div>
  );
}

function ListBody() {
  const navigate = useNavigate();
  const { state, retry } = useRooms(null);

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 px-6 py-8">
      <section aria-label="검토 방 목록">
        <h1 className="mb-3 text-[20px] font-semibold text-slate-800">자소서 검토 방</h1>

        {state.status === 'loading' && (
          <p className="text-[14px] text-slate-400" role="status">
            불러오는 중…
          </p>
        )}

        {state.status === 'error' && (
          <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4">
            <p className="text-[14px] font-medium text-red-700">{state.error.message}</p>
            <button
              type="button"
              onClick={retry}
              className="mt-2 text-[13px] font-semibold text-red-700 underline"
            >
              다시 시도
            </button>
          </div>
        )}

        {state.status === 'success' &&
          (state.data.length === 0 ? (
            <p className="text-[14px] text-slate-400">
              아직 만든 방이 없습니다. 아래에서 첫 방을 만들어 보세요.
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {state.data.map((room) => (
                <li key={room.roomId}>
                  <button
                    type="button"
                    onClick={() => navigate(`/agent-rooms/${room.roomId}`)}
                    className="flex w-full items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-left transition hover:border-slate-300"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-[15px] font-semibold text-slate-800">
                        {room.title}
                      </span>
                      <span className="block truncate text-[12px] text-slate-500">
                        {room.lastMessagePreview ?? '아직 대화가 없습니다'}
                      </span>
                    </span>
                    <span className="shrink-0 text-[12px] text-slate-400">
                      에이전트 {room.agentCount}
                      {room.running && (
                        <span className="ml-1.5 font-semibold text-blue-600">진행 중</span>
                      )}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ))}
      </section>

      <RoomCreateForm onCreated={(roomId) => navigate(`/agent-rooms/${roomId}`)} />
    </div>
  );
}

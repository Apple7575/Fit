import { LoadingScreen } from '../../components/brand/LoadingScreen';
import { Link, Navigate, useParams } from 'react-router-dom';
import { CoverLetterHeader } from '../cover-letter/CoverLetterHeader';
import { useAuth } from '../../features/auth/AuthProvider';
import { RoomWorkspace } from '../../features/agent-room/RoomWorkspace';

/** 검토 방 한 개. 참여 에이전트와 설정을 본다. */
export function AgentRoomPage() {
  const { user, loading } = useAuth();
  const { roomId } = useParams();
  const parsed = Number(roomId);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50">
        <CoverLetterHeader />
        <LoadingScreen />
      </div>
    );
  }

  if (!user) return <Navigate replace to="/login" />;
  if (!Number.isInteger(parsed) || parsed <= 0) return <Navigate replace to="/agent-rooms" />;

  return (
    <div className="min-h-screen bg-slate-50">
      <CoverLetterHeader />
      <div className="mx-auto max-w-4xl px-6 py-8">
        <Link to="/agent-rooms" className="text-[13px] font-medium text-slate-500 hover:text-slate-700">
          ← 검토 방 목록
        </Link>
        <div className="mt-4">
          <RoomWorkspace roomId={parsed} />
        </div>
      </div>
    </div>
  );
}

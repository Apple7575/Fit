import { LoadingScreen } from '../../components/brand/LoadingScreen';
import { SiteHeader } from '../../components/layout/SiteHeader';
import { useCallback, useEffect, useState } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { ApiError } from '../../api/client';
import { ensureDefaultRooms } from '../../features/agent-room/api';
import { RoomWorkspace } from '../../features/agent-room/RoomWorkspace';
import { ThreadSidebar } from '../../features/agent-room/ThreadSidebar';
import type { RoomSummary } from '../../features/agent-room/types';
import { useAuth } from '../../features/auth/AuthProvider';
import { useCoverLetters } from '../../features/cover-letter/queries';

/** 자소서를 고르면 에이전트별 대화 자리가 깔리고, 원문 옆에서 피드백을 확인한다. */
export function AgentRoomListPage() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50">
        <SiteHeader />
        <LoadingScreen />
      </div>
    );
  }

  // 방은 저장되는 것이라 로그인해야 한다.
  if (!user) return <Navigate replace to="/login" />;

  return (
    <div className="min-h-screen bg-slate-50">
      <SiteHeader />
      <Workspace />
    </div>
  );
}

function Workspace() {
  const [searchParams] = useSearchParams();
  const { state: coverLetters } = useCoverLetters();
  // 작성 화면에서 'AI 검토' 로 넘어오면 방금 저장한 자소서를 연다.
  const requested = Number(searchParams.get('coverLetterId')) || null;
  const [picked, setPicked] = useState<number | null>(requested);
  const [rooms, setRooms] = useState<RoomSummary[]>([]);
  const [selectedRoomId, setSelectedRoomId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryToken, setRetryToken] = useState(0);

  const letters = coverLetters.status === 'success' ? coverLetters.data : [];
  // 고르지 않았으면 첫 자소서로 본다. 효과로 상태를 채우지 않고 렌더에서 정한다.
  // 넘어온 id 가 이 회원 것이 아니면 무시한다 — 남의 id 로 방을 깔면 404 만 난다.
  const known = picked !== null && letters.some((letter) => letter.id === picked);
  const coverLetterId = known ? picked : letters.length > 0 ? letters[0].id : null;

  /** 에이전트 목록만 다시 읽는다. 보고 있던 방은 그대로 둔다. */
  const refreshRooms = useCallback(() => {
    if (coverLetterId === null) return;
    ensureDefaultRooms(coverLetterId)
      .then((next) => setRooms(next))
      .catch(() => {
        // 목록 갱신 실패는 대화를 막지 않는다. 다음 갱신 때 따라온다.
      });
  }, [coverLetterId]);

  // 자소서를 고르면 대화 자리를 깔고 함께 논의하는 방을 먼저 연다.
  useEffect(() => {
    if (coverLetterId === null) return;
    let cancelled = false;

    ensureDefaultRooms(coverLetterId)
      .then((next) => {
        if (cancelled) return;
        setRooms(next);
        setError(null);
        const preferred = next.find((room) => room.agentCount > 1) ?? next[0];
        setSelectedRoomId(preferred ? preferred.roomId : null);
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        setError(caught instanceof ApiError ? caught.message : '대화 목록을 불러오지 못했습니다.');
      });

    return () => {
      cancelled = true;
    };
  }, [coverLetterId, retryToken]);

  if (coverLetters.status === 'success' && letters.length === 0) {
    return (
      <p className="mx-auto max-w-4xl px-6 py-16 text-center text-[14px] text-slate-400">
        저장된 자소서가 없습니다. 자기소개서를 먼저 저장해 주세요.
      </p>
    );
  }

  const coverLetterSelector = (
    <section aria-label="자기소개서 에이전트 목록" className="rounded-2xl border border-slate-200 bg-white p-3 pt-10">
        <div>
          <label htmlFor="workspace-cover-letter" className="sr-only">
            검토할 자소서
          </label>
          <select
            id="workspace-cover-letter"
            value={coverLetterId ?? ''}
            onChange={(event) => setPicked(Number(event.target.value))}
            className="h-[36px] w-full rounded-lg border border-slate-200 bg-white py-0 pl-2 pr-10 text-[13px] text-slate-800"
          >
            {letters.map((letter) => (
              <option key={letter.id} value={letter.id}>
                {letter.title}
              </option>
            ))}
          </select>
        </div>

        {error && (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3">
            <p className="text-[13px] font-medium text-red-700">{error}</p>
            <button
              type="button"
              onClick={() => setRetryToken((n) => n + 1)}
              className="mt-1 text-[12px] font-semibold text-red-700 underline"
            >
              다시 시도
            </button>
          </div>
        )}
    </section>
  );

  const agentNavigation = error ? null : (
    <ThreadSidebar
      rooms={rooms}
      selectedRoomId={selectedRoomId}
      onSelect={setSelectedRoomId}
    />
  );

  return (
    <main className="mx-auto max-w-[1520px] px-5 py-6 lg:px-8">
      {selectedRoomId === null ? (
        <div className="ml-auto max-w-md">
          {coverLetterSelector}
          {!error && (
            <div className="mt-3">
              <ThreadSidebar
                rooms={rooms}
                selectedRoomId={selectedRoomId}
                onSelect={setSelectedRoomId}
              />
            </div>
          )}
          <p role="status" className="mt-4 text-[14px] text-slate-400">대화를 고르세요.</p>
        </div>
      ) : (
        <RoomWorkspace
          key={selectedRoomId}
          roomId={selectedRoomId}
          coverLetterSelector={coverLetterSelector}
          agentNavigation={agentNavigation}
          onConversationChanged={refreshRooms}
        />
      )}
    </main>
  );
}

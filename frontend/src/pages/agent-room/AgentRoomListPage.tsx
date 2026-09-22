import { LoadingScreen } from '../../components/brand/LoadingScreen';
import { SiteHeader } from '../../components/layout/SiteHeader';
import { useCallback, useEffect, useState } from 'react';
import { Link, Navigate, useSearchParams } from 'react-router-dom';
import { ApiError } from '../../api/client';
import { ensureDefaultRooms } from '../../features/agent-room/api';
import { CoverLetterSwitcher } from '../../features/agent-room/CoverLetterSwitcher';
import { RoomBackdrop, RoomEntry } from '../../features/agent-room/RoomEntry';
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

  /*
   * 헤더는 화면마다 다르게 선다 — 입장 화면(RoomEntry)은 사진 위에 투명하게 띄우고,
   * 읽는 화면은 흰 띠로 세운다. 그래서 여기서 한 번에 그리지 않고 각 화면이 그린다.
   */
  return <Workspace />;
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

  /*
   * 자소서를 고르면 대화 자리를 깔아 둔다.
   *
   * <p>바로 방까지 열어 버리는 것은 작성 화면에서 'AI 검토' 로 넘어온 경우뿐이다 — 그때는
   * 무엇을 볼지 이미 고르고 온 것이라 한 번 더 묻는 것이 군더더기다. 주소로 그냥 들어온
   * 경우에는 입장 화면에 세워 어느 자소서를 누구의 눈으로 볼지 먼저 고르게 한다.
   */
  const autoEnter = requested !== null;

  useEffect(() => {
    if (coverLetterId === null) return;
    let cancelled = false;

    ensureDefaultRooms(coverLetterId)
      .then((next) => {
        if (cancelled) return;
        setRooms(next);
        setError(null);
        if (!autoEnter) return;
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
  }, [autoEnter, coverLetterId, retryToken]);

  if (coverLetters.status === 'success' && letters.length === 0) {
    return (
      <RoomEntry
        description="검토할 자소서가 아직 없습니다. 자소서를 하나 저장하면 코치 다섯이 각자 맡은 자료로 읽기 시작합니다."
        title="먼저 자소서가 필요해요"
      >
        <div className="text-center">
          <Link
            className="inline-block rounded-full bg-white px-7 py-3 text-sm font-bold text-slate-950 transition hover:-translate-y-0.5 hover:shadow-lg"
            to="/cover-letters/new"
          >
            자소서 쓰러 가기
          </Link>
        </div>
      </RoomEntry>
    );
  }

  const coverLetterSelector = (
    <section aria-label="자기소개서 에이전트 목록" className="min-w-0">
        <CoverLetterSwitcher letters={letters} onSelect={setPicked} selectedId={coverLetterId} />

        {error && (
          <div role="alert" className="mt-2 rounded-lg border border-red-200 bg-red-50 p-3">
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

  /*
   * 아직 방을 고르지 않았다. 예전에는 "대화를 고르세요" 회색 글자 한 줄이 전부라, 기능의
   * 첫인상이 빈 화면이었다. 고르고 넘어가는 자리이므로 다른 첫 화면들과 같은 짜임으로 세운다.
   */
  if (selectedRoomId === null) {
    return (
      <RoomEntry
        description="코치 다섯이 각자 맡은 자료로 한 자소서를 읽습니다. 어느 자소서를 볼지 고르세요."
        title="누구의 눈으로 볼까요?"
      >
        <section
          aria-label="검토할 자소서"
          className="rounded-2xl bg-white/10 p-4 ring-1 ring-white/20 backdrop-blur"
        >
          <p className="mb-2 text-[12px] font-semibold text-white/60">검토할 자소서</p>
          {coverLetterSelector}
        </section>
        {!error && (
          <div className="mt-4">
            <ThreadSidebar onSelect={setSelectedRoomId} rooms={rooms} selectedRoomId={selectedRoomId} wrap />
          </div>
        )}
      </RoomEntry>
    );
  }

  /*
   * 읽는 화면도 같은 바탕 위에 선다. 자소서 원문과 대화는 흰 카드 안에 있으므로 사진이
   * 글 뒤로 오지 않는다 — 카드가 뜨는 자리만 사진이다.
   */
  return (
    <div className="relative isolate min-h-screen bg-slate-100">
      <RoomBackdrop tone="light" />
      <SiteHeader />
      <main className="relative mx-auto max-w-[1520px] px-5 py-6 lg:px-8">
        <RoomWorkspace
          key={selectedRoomId}
          roomId={selectedRoomId}
          coverLetterSelector={coverLetterSelector}
          agentNavigation={agentNavigation}
          onConversationChanged={refreshRooms}
        />
      </main>
    </div>
  );
}

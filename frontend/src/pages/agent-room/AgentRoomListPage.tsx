import { LoadingScreen } from '../../components/brand/LoadingScreen';
import { SiteHeader } from '../../components/layout/SiteHeader';
import { useCallback, useEffect, useState } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { userMessage } from '../../api/errorMessage';
import { ensureDefaultRooms } from '../../features/agent-room/api';
import { RoomBackdrop, RoomEntry } from '../../features/agent-room/RoomEntry';
import { CoverLetterHeader } from '../cover-letter/CoverLetterHeader';
import { RoomWorkspace } from '../../features/agent-room/RoomWorkspace';
import { ThreadSidebar } from '../../features/agent-room/ThreadSidebar';
import type { RoomSummary } from '../../features/agent-room/types';
import { useAuth } from '../../features/auth/AuthProvider';
import { useCoverLetters } from '../../features/cover-letter/queries';

/**
 * 자소서 한 건의 검토 면. 코치를 고르면 원문 옆에서 피드백을 확인한다.
 *
 * <p>어느 자소서를 볼지는 주소가 정한다(`/cover-letters/:id/review`). 예전에는 이 화면이
 * `/agent-rooms` 라는 독립 주소였고 자소서는 화면 안에서 골랐는데, 자소서를 고르지 않고
 * 들어오면 말없이 첫 자소서로 떨어졌다 — 무엇을 보고 있는지 알 수 없었다.
 */
export function AgentRoomListPage() {
  const { user, loading } = useAuth();
  const { id } = useParams();
  const coverLetterId = Number(id) || null;

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50">
        <SiteHeader />
        <LoadingScreen />
      </div>
    );
  }

  // 방은 저장되는 것이라 로그인해야 한다.
  if (!user) return <Navigate replace to={`/login?redirect=/cover-letters/${id}/review`} />;
  if (coverLetterId === null) return <Navigate replace to="/cover-letters" />;

  /*
   * 헤더는 화면마다 다르게 선다 — 입장 화면(RoomEntry)은 사진 위에 띄우고, 읽는 화면은
   * 흰 띠로 세운다. 그래서 여기서 한 번에 그리지 않고 각 화면이 그린다.
   */
  return <Workspace coverLetterId={coverLetterId} />;
}

function Workspace({ coverLetterId }: { coverLetterId: number }) {
  const { state: coverLetters } = useCoverLetters();
  const [rooms, setRooms] = useState<RoomSummary[]>([]);
  const [selectedRoomId, setSelectedRoomId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryToken, setRetryToken] = useState(0);

  const letters = coverLetters.status === 'success' ? coverLetters.data : [];
  // 주소의 자소서. 이 회원 것이 아니면 방을 깔지 않는다 — 남의 id 로 깔면 404 만 난다.
  const letter = letters.find((item) => item.id === coverLetterId) ?? null;
  const mine = coverLetters.status !== 'success' || letter !== null;
  // 자소서 이름표를 단 띠. 검토에서 작성으로 돌아가는 길이 여기에만 있다.
  const header = letter ? <CoverLetterHeader letter={letter} /> : undefined;

  /** 에이전트 목록만 다시 읽는다. 보고 있던 방은 그대로 둔다. */
  const refreshRooms = useCallback(() => {
    ensureDefaultRooms(coverLetterId)
      .then((next) => setRooms(next))
      .catch(() => {
        // 목록 갱신 실패는 대화를 막지 않는다. 다음 갱신 때 따라온다.
      });
  }, [coverLetterId]);

  /*
   * 대화 자리를 깔고 바로 연다.
   *
   * <p>예전에는 "누구의 눈으로 볼까요?" 한 장을 거쳤다. 그런데 거기서 하는 일(코치 고르기)은
   * 대화 화면 안에도 그대로 있다 — 채팅 패널 위의 칩 줄이 같은 목록이다. 같은 것을 고르려고
   * 화면을 한 번 더 넘기게 할 이유가 없다. 총괄 논의부터 연다(없으면 첫 방).
   */
  useEffect(() => {
    if (!mine) return;
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
        setError(userMessage(caught, '대화 목록을 불러오지 못했습니다.'));
      });

    return () => {
      cancelled = true;
    };
  }, [coverLetterId, mine, retryToken]);

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

  /*
   * 어느 자소서를 볼지 고르는 드롭다운이 여기 있었다. 주소가 자소서를 정하게 되면서 없앴다 —
   * 기업 상세에서 기업을 바꾸지 않고 검색으로 돌아가는 것과 같다. 다른 자소서는 목록에서 연다.
   */
  const roomsError = error && (
    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3">
      <p className="text-[13px] font-medium text-red-700">{error}</p>
      <button
        className="mt-1 text-[12px] font-semibold text-red-700 underline"
        onClick={() => setRetryToken((n) => n + 1)}
        type="button"
      >
        다시 시도
      </button>
    </div>
  );

  const agentNavigation = error ? null : (
    <ThreadSidebar
      rooms={rooms}
      selectedRoomId={selectedRoomId}
      onSelect={setSelectedRoomId}
    />
  );

  // 방을 까는 동안. 고를 것이 없으므로 기다린다는 말만 한다
  if (selectedRoomId === null) {
    return (
      <div className="relative isolate min-h-screen bg-slate-950">
        <RoomBackdrop tone="read" />
        {header ?? <SiteHeader />}
        <main className="relative mx-auto max-w-[1520px] px-5 py-6 lg:px-8">
          {error ? roomsError : <LoadingScreen message="검토 방을 여는 중" onDark />}
        </main>
      </div>
    );
  }

  /*
   * 읽는 화면도 같은 바탕 위에 선다. 자소서 원문과 대화는 흰 카드 안에 있으므로 사진이
   * 글 뒤로 오지 않는다 — 카드가 뜨는 자리만 사진이다.
   */
  return (
    // 사진이 오기 전에 깔리는 바탕. 밝게 두면 사진이 붙는 순간 화면이 한 번 어두워진다
    <div className="relative isolate min-h-screen bg-slate-950">
      <RoomBackdrop tone="read" />
      {header ?? <SiteHeader />}
      <main className="relative mx-auto max-w-[1520px] px-5 py-6 lg:px-8">
        {/*
          key 를 걸어 방마다 새로 마운트했었다. 그러면 코치를 바꿀 때마다 자소서 원문까지
          함께 헐렸다가 다시 붙어 화면이 깜빡였다. 바뀌는 것은 대화뿐이다.
        */}
        <RoomWorkspace
          roomId={selectedRoomId}
          coverLetterSelector={roomsError || null}
          agentNavigation={agentNavigation}
          onConversationChanged={refreshRooms}
        />
      </main>
    </div>
  );
}

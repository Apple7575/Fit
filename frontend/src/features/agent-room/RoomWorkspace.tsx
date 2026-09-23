import { LoadingScreen } from '../../components/brand/LoadingScreen';
import { useEffect, useRef, useState, type ReactNode, type UIEvent } from 'react';
import { Link } from 'react-router-dom';
import { ApiError, isNotFound, isRateLimited } from '../../api/client';
import { sendMessage } from './api';
import { DocumentPanel } from './DocumentPanel';
import { MessageComposer } from './MessageComposer';
import { MessageThread } from './MessageThread';
import { useOptionalCoverLetter } from '../cover-letter/queries';
import { useRoom } from './queries';
import { useLiveMessages } from './useLiveMessages';
import { useTurnPolling } from './useTurnPolling';
import type { Room } from './types';

interface RoomWorkspaceProps {
  roomId: number;
  coverLetterSelector?: ReactNode;
  agentNavigation?: ReactNode;
  /** 대화가 끝나 에이전트 목록의 미리보기가 바뀌었을 때 알린다. */
  onConversationChanged?: () => void;
}

/** 검토 방 한 개. 참여 에이전트와 대화. */
export function RoomWorkspace({ roomId, coverLetterSelector, agentNavigation, onConversationChanged }: RoomWorkspaceProps) {
  const { state: room, retry: reloadRoom } = useRoom(roomId);
  const { state: messages, reload: reloadMessages } = useLiveMessages(roomId);
  /*
   * 돌고 있는 턴은 그 방의 것이다. 방마다 새로 마운트하던 때에는 저절로 비워졌지만, 이제
   * 한 컴포넌트가 방을 갈아 끼우므로 어느 방의 턴인지 함께 들고 있다가 방이 바뀌면 버린다.
   * (효과로 비우면 한 번 더 그려야 하므로 그릴 때 판단한다)
   */
  const [runningTurn, setRunningTurn] = useState<{ roomId: number; turnId: number | null }>({
    roomId,
    turnId: null,
  });
  const activeTurnId = runningTurn.roomId === roomId ? runningTurn.turnId : null;
  const setActiveTurnId = (turnId: number | null) => setRunningTurn({ roomId, turnId });

  const turn = useTurnPolling(roomId, activeTurnId, () => {
    setActiveTurnId(null);
    reloadMessages();
    // 마지막 대화 시각이 바뀌므로 방과 에이전트 목록도 다시 읽는다.
    reloadRoom();
    onConversationChanged?.();
  });

  if (room.status === 'loading') {
    return <LoadingScreen compact message="검토 방을 여는 중" />;
  }
  if (room.status === 'error') {
    // 없거나 접근 불가한 방(404 ROOM_NOT_FOUND)은 재시도해도 같은 404 → 목록으로 유도한다.
    if (isNotFound(room.error)) {
      return (
        <div role="alert" className="rounded-xl border border-slate-200 bg-slate-50 p-4">
          <p className="text-[14px] font-medium text-slate-700">검토 방을 찾을 수 없습니다.</p>
          <Link
            to="/cover-letters"
            className="mt-2 inline-block text-[13px] font-semibold text-blue-600 underline"
          >
            검토 방 목록으로
          </Link>
        </div>
      );
    }
    return (
      <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4">
        <p className="text-[14px] font-medium text-red-700">{room.error.message}</p>
        <button
          type="button"
          onClick={reloadRoom}
          className="mt-2 text-[13px] font-semibold text-red-700 underline"
        >
          다시 시도
        </button>
      </div>
    );
  }

  return (
    <RoomBody
      data={room.data}
      coverLetterSelector={coverLetterSelector}
      agentNavigation={agentNavigation}
      messages={messages}
      onStarted={setActiveTurnId}
      reloadMessages={reloadMessages}
      roomId={roomId}
      turn={turn}
      turnId={activeTurnId}
    />
  );
}

/** 방이 확정된 뒤의 본문. 자소서 원문을 왼쪽에, 에이전트 대화를 오른쪽에 둔다. */
function RoomBody({
  data,
  coverLetterSelector,
  agentNavigation,
  messages,
  turn,
  turnId,
  roomId,
  reloadMessages,
  onStarted,
}: {
  data: Room;
  coverLetterSelector?: ReactNode;
  agentNavigation?: ReactNode;
  messages: ReturnType<typeof useLiveMessages>['state'];
  turn: ReturnType<typeof useTurnPolling>;
  turnId: number | null;
  roomId: number;
  reloadMessages: () => void;
  onStarted: (id: number) => void;
}) {
  const messageViewport = useRef<HTMLDivElement>(null);
  const followLatestMessage = useRef(true);
  const [chatOpen, setChatOpen] = useState(true);
  const [closedAtMessageCount, setClosedAtMessageCount] = useState(0);
  const [selection, setSelection] = useState<{ coverLetterId: number; itemId: number } | null>(null);
  const [reviewingItemId, setReviewingItemId] = useState<number | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);
  // 자소서 원문은 여기서 한 번만 부른다.
  const doc = useOptionalCoverLetter(data.coverLetter?.id ?? null);
  const agentNames = Object.fromEntries(data.agents.map((agent) => [agent.agentKey, agent.name]));
  const items = doc.state.status === 'success' ? doc.state.data.items : [];
  const selectedCandidateId =
    selection && selection.coverLetterId === data.coverLetter?.id ? selection.itemId : null;
  const selectedItemId =
    items.length === 1
      ? items[0].id
      : selectedCandidateId !== null && items.some((item) => item.id === selectedCandidateId)
        ? selectedCandidateId
        : null;
  const selectedItemNumber =
    selectedItemId === null ? null : items.findIndex((item) => item.id === selectedItemId) + 1;
  const hasWritingAgent = data.agents.some((agent) => agent.agentKey === 'writing');

  // 서버는 최신순으로 주는데 화면은 위에서 아래로 읽는다.
  const thread = messages.status === 'success' ? [...messages.data.messages].reverse() : [];
  // 자동 검토가 도는 중일 수도 있다. 그때 말을 걸면 서버가 409 로 막으므로 미리 잠근다.
  const busy =
    turnId !== null ||
    thread.some((message) => message.status === 'PENDING' || message.status === 'RUNNING');

  const lastMessage = thread.at(-1);
  const waitingCount = (turn?.agents.length ?? 0) + (turn?.supervisor ? 1 : 0);
  const unreadCount = Math.max(0, thread.length - closedAtMessageCount);

  // 채팅을 처음 열거나 새 답을 기다리는 동안에는 최신 메시지를 보여 준다. 사용자가 이전
  // 대화를 읽으려고 위로 올렸다면 자동으로 끌어내리지 않는다.
  useEffect(() => {
    const viewport = messageViewport.current;
    if (!viewport || !followLatestMessage.current) return;
    viewport.scrollTo({ top: viewport.scrollHeight, behavior: 'smooth' });
  }, [chatOpen, lastMessage?.messageId, lastMessage?.status, waitingCount]);

  const rememberScrollPosition = (event: UIEvent<HTMLDivElement>) => {
    const viewport = event.currentTarget;
    followLatestMessage.current =
      viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight < 80;
  };

  const handleStarted = (id: number) => {
    followLatestMessage.current = true;
    onStarted(id);
  };

  const reviewItem = async (itemId: number) => {
    if (busy || reviewingItemId !== null || !data.coverLetter) return;

    setSelection({ coverLetterId: data.coverLetter.id, itemId });
    setChatOpen(true);
    followLatestMessage.current = true;
    setReviewingItemId(itemId);
    setReviewError(null);
    try {
      const started = await sendMessage(
        roomId,
        '선택한 자기소개서 문항을 글쓰기 담당 관점에서 검토해 주세요.',
        itemId,
      );
      handleStarted(started.turnId);
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === 'TURN_IN_PROGRESS') {
        setReviewError('이미 검토가 진행 중입니다. 완료된 뒤 다시 요청해 주세요.');
        reloadMessages();
      } else if (caught instanceof ApiError && isRateLimited(caught)) {
        setReviewError('요청이 많습니다. 잠시 후 다시 시도해 주세요.');
      } else {
        setReviewError(
          caught instanceof ApiError
            ? caught.message
            : '검토를 시작하지 못했습니다. 잠시 후 다시 시도해 주세요.',
        );
      }
    } finally {
      setReviewingItemId(null);
    }
  };

  return (
    <div
      className={`min-w-0 transition-[padding] duration-300 ${
        data.coverLetter && chatOpen ? 'xl:pr-[454px]' : ''
      }`}
    >
      {data.coverLetter && (
        <section className="min-w-0" aria-label="검토 중인 자소서">
          <DocumentPanel
            retry={doc.retry}
            state={doc.state}
            selectedItemId={selectedItemId}
            onReviewItem={(itemId) => void reviewItem(itemId)}
            reviewingItemId={reviewingItemId}
            reviewBusy={busy || reviewingItemId !== null}
            reviewError={reviewError}
          />
        </section>
      )}

      {chatOpen ? (
        <aside
          aria-label="AI 에이전트 피드백"
          className="fixed inset-x-3 bottom-3 top-3 z-40 min-w-0 xl:inset-x-auto xl:bottom-6 xl:right-8 xl:top-[72px] xl:z-20 xl:w-[430px]"
        >
          <div className="relative z-10 flex h-full min-h-0 flex-col overflow-hidden rounded-3xl border border-slate-200 bg-slate-50 shadow-2xl">
            <div className="flex shrink-0 items-start gap-2 bg-slate-50 p-3">
              <div className="min-w-0 flex-1">{coverLetterSelector}</div>
              <button
                type="button"
                aria-label="AI 피드백 닫기"
                onClick={() => {
                  setClosedAtMessageCount(thread.length);
                  setChatOpen(false);
                }}
                className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-xl leading-none text-slate-400 transition hover:bg-slate-200/60 hover:text-slate-800"
              >
                ×
              </button>
            </div>

            <div className="shrink-0 border-b border-slate-200 bg-slate-50 px-3 pb-3">
              {agentNavigation}
            </div>

            <section aria-label="에이전트와 대화" className="flex min-h-0 flex-1 flex-col bg-white">

            <div
              ref={messageViewport}
              onScroll={rememberScrollPosition}
              className="min-h-0 flex-1 overflow-y-auto bg-slate-50/60 px-4 py-4 overscroll-contain"
            >
              {messages.status === 'error' && (
                <div role="alert" className="mb-4 rounded-xl border border-red-200 bg-red-50 p-3">
                  <p className="text-[13px] font-medium text-red-700">{messages.error.message}</p>
                  <button
                    type="button"
                    onClick={reloadMessages}
                    className="mt-1 text-[12px] font-semibold text-red-700 underline"
                  >
                    다시 시도
                  </button>
                </div>
              )}

              <MessageThread messages={thread} running={turn} agentNames={agentNames} />
            </div>

            <MessageComposer
              roomId={roomId}
              coverLetterItemId={selectedItemId}
              selectedItemNumber={selectedItemNumber}
              needsItemSelection={hasWritingAgent && items.length > 1 && selectedItemId === null}
              busy={busy}
              onStarted={handleStarted}
              onConflict={reloadMessages}
            />
            </section>
          </div>
        </aside>
      ) : (
        <button
          type="button"
          onClick={() => {
            followLatestMessage.current = true;
            setChatOpen(true);
          }}
          className="fixed bottom-6 right-5 z-20 inline-flex items-center gap-2 rounded-full bg-blue-600 px-5 py-3 text-[14px] font-bold text-white shadow-xl transition hover:bg-blue-700 lg:right-8"
        >
          AI 피드백 열기
          {unreadCount > 0 && (
            <span className="grid min-w-5 place-items-center rounded-full bg-white px-1.5 py-0.5 text-[11px] text-blue-700">
              {unreadCount > 99 ? '99+' : unreadCount}
            </span>
          )}
          {busy && unreadCount === 0 && <span className="h-2 w-2 animate-pulse rounded-full bg-white" />}
        </button>
      )}
    </div>
  );
}

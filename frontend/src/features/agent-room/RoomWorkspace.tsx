import { CharacterSlot } from '../../components/brand/CharacterSlot';
import { characterForAgent } from '../../components/brand/characters';
import { LoadingScreen } from '../../components/brand/LoadingScreen';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { isNotFound } from '../../api/client';
import { agentSource } from './agentSource';
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
  /** 대화가 끝나 사이드바의 미리보기가 바뀌었을 때 알린다. */
  onConversationChanged?: () => void;
}

/** 검토 방 한 개. 참여 에이전트와 대화. */
export function RoomWorkspace({ roomId, onConversationChanged }: RoomWorkspaceProps) {
  const { state: room, retry: reloadRoom } = useRoom(roomId);
  const { state: messages, reload: reloadMessages } = useLiveMessages(roomId);
  const [activeTurnId, setActiveTurnId] = useState<number | null>(null);

  const turn = useTurnPolling(roomId, activeTurnId, () => {
    setActiveTurnId(null);
    reloadMessages();
    // 마지막 대화 시각이 바뀌므로 방과 사이드바도 다시 읽는다.
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
            to="/agent-rooms"
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
      messages={messages}
      onStarted={setActiveTurnId}
      reloadMessages={reloadMessages}
      roomId={roomId}
      turn={turn}
      turnId={activeTurnId}
    />
  );
}

/** 방이 확정된 뒤의 본문. 자소서 원문은 여기서 한 번만 불러 두 자리에 나눠 준다 */
function RoomBody({
  data,
  messages,
  turn,
  turnId,
  roomId,
  reloadMessages,
  onStarted,
}: {
  data: Room;
  messages: ReturnType<typeof useLiveMessages>['state'];
  turn: ReturnType<typeof useTurnPolling>;
  turnId: number | null;
  roomId: number;
  reloadMessages: () => void;
  onStarted: (id: number) => void;
}) {
  // 자소서 원문은 여기서 한 번만 부른다 (넓은 화면의 오른쪽 칸과 접이식 자리가 함께 쓴다)
  const doc = useOptionalCoverLetter(data.coverLetter?.id ?? null);
  const agentNames = Object.fromEntries(data.agents.map((agent) => [agent.agentKey, agent.name]));
  // 참여 못 하는 담당. 판단은 서버가 준 ready 하나만 쓴다 (실제로 도는 조건은 백엔드가 안다)
  const idleAgents = data.agents.filter((agent) => !agent.ready);

  // 서버는 최신순으로 주는데 화면은 위에서 아래로 읽는다.
  const thread = messages.status === 'success' ? [...messages.data.messages].reverse() : [];
  // 자동 검토가 도는 중일 수도 있다. 그때 말을 걸면 서버가 409 로 막으므로 미리 잠근다.
  const busy =
    turnId !== null ||
    thread.some((message) => message.status === 'PENDING' || message.status === 'RUNNING');

  return (
    // 왼쪽은 대화, 오른쪽은 검토 중인 자소서 원문. 좁은 화면에서는 원문을 대화 위로 접어 둔다.
    <div className="flex min-w-0 gap-5">
      <div className="flex min-w-0 flex-1 flex-col gap-4">
        <header>
          <h2 className="text-[18px] font-semibold text-slate-800">{data.title}</h2>
          <p className="mt-0.5 text-[13px] text-slate-500">
            {data.coverLetter ? data.coverLetter.title : '연결된 자소서 없음'}
            <span className="mx-1.5 text-slate-300">·</span>
            에이전트 {data.agents.length}명
            {data.jobContext && (
              <>
                <span className="mx-1.5 text-slate-300">·</span>
                공고 {data.jobContext.companyName} {data.jobContext.positionName}
              </>
            )}
          </p>
        </header>

        {/* 담당을 이름이 아니라 "무엇을 읽는지"로 소개한다 */}
        <ul aria-label="참여 에이전트" className="grid gap-1.5 sm:grid-cols-2">
          {data.agents.map((agent) => {
            const source = agentSource(agent, data.jobContext);
            const idle = !agent.ready;
            return (
              <li
                className={`flex items-start gap-2 rounded-xl border px-3 py-2 ${
                  idle ? 'border-slate-200 bg-slate-50' : 'border-slate-200 bg-white'
                }`}
                key={agent.agentKey}
              >
                <span className={`mt-0.5 shrink-0 ${idle ? 'opacity-50' : ''}`}>
                  <CharacterSlot character={characterForAgent(agent.agentKey)} interactive={false} size={18} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5">
                    <span className={`text-[12px] font-semibold ${idle ? 'text-slate-500' : 'text-slate-800'}`}>
                      {agent.name}
                    </span>
                    {agent.auto && <span className="text-[11px] text-slate-400">자동</span>}
                  </span>
                  <span className="mt-0.5 block text-[11px] break-keep text-slate-500">
                    {source.reads}
                  </span>
                  {idle && (
                    <span className="mt-0.5 block text-[11px] break-keep text-slate-400">{source.need}</span>
                  )}
                </span>
              </li>
            );
          })}
        </ul>

        {/*
          빠진 담당 안내. 이미 만들어진 방은 만들 때 정해진 자료를 그대로 쓰므로
          (RoomService.defaultConfig 은 방 생성 때만 돈다) "자소서를 고치면 지금 방이 바뀐다"고
          적으면 거짓말이 된다. 언제 반영되는지까지 적는다.
        */}
        {data.coverLetter && idleAgents.length > 0 && (
          <p className="rounded-xl bg-slate-50 px-3 py-2 text-[12px] break-keep text-slate-500">
            {idleAgents.map((agent) => agent.name).join(', ')}
            은 지금 방에서 참여하지 않아요. 이 방은 만들 때 정해진 자료를 그대로 씁니다.{' '}
            <Link className="font-semibold text-blue-600 hover:underline" to={`/cover-letters/${data.coverLetter.id}`}>
              자소서 고치기
            </Link>
            를 누르면 다음에 여는 방부터 반영돼요.
          </p>
        )}

        {messages.status === 'error' && (
          <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3">
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

        {data.coverLetter && (
          <details className="rounded-2xl border border-slate-200 bg-white xl:hidden">
            <summary className="cursor-pointer px-4 py-3 text-[13px] font-semibold text-slate-700">
              검토 중인 자소서 보기
            </summary>
            <div className="border-t border-slate-100">
              <DocumentPanel framed={false} retry={doc.retry} state={doc.state} />
            </div>
          </details>
        )}

        <MessageThread messages={thread} running={turn} agentNames={agentNames} />

        <MessageComposer
          roomId={roomId}
          busy={busy}
          onStarted={onStarted}
          onConflict={reloadMessages}
        />
      </div>

      {data.coverLetter && (
        <aside className="hidden w-[340px] shrink-0 xl:block">
          <div className="sticky top-20 max-h-[calc(100vh-6rem)] overflow-y-auto">
            <DocumentPanel retry={doc.retry} state={doc.state} />
          </div>
        </aside>
      )}
    </div>
  );
}

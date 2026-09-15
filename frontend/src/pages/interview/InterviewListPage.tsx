import { LoadingScreen } from '../../components/brand/LoadingScreen';
import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { InlineNotice } from '../../components/common/InlineNotice';
import { useAuth } from '../../features/auth/AuthProvider';
import { deleteInterview } from '../../features/interview/api';
import { useInterviews } from '../../features/interview/queries';
import { TYPE_LABEL } from '../../features/interview/styles';
import type { InterviewSummary } from '../../features/interview/types';
import { InterviewHeader } from './InterviewHeader';

export function InterviewListPage() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50">
        <InterviewHeader />
        <LoadingScreen />
      </div>
    );
  }

  // 모의 면접은 로그인 전용이다. 게스트는 로그인으로 보낸다.
  if (!user) return <Navigate replace to="/login?redirect=/interviews" />;

  return (
    <div className="min-h-screen bg-slate-50">
      <InterviewHeader />
      <ListBody />
    </div>
  );
}

function ListBody() {
  const navigate = useNavigate();
  const { state, retry } = useInterviews();
  const [confirmingId, setConfirmingId] = useState<number | null>(null);

  const remove = async (id: number) => {
    setConfirmingId(null);
    await deleteInterview(id);
    retry();
  };

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-950">내 모의 면접</h1>
          <p className="mt-1 text-sm text-slate-500">
            면접을 선택해 결과를 다시 보거나, 새 면접을 시작하세요. 결과는 나에게만 보입니다.
          </p>
        </div>
        <button
          onClick={() => navigate('/interviews/new')}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700"
          type="button"
        >
          + 새 면접
        </button>
      </div>

      {state.status === 'loading' && (
        <div className="rounded-2xl border border-slate-200 bg-white">
          <LoadingScreen compact message="면접 기록을 불러오는 중" />
        </div>
      )}

      {state.status === 'error' && (
        <InlineNotice onRetry={retry}>목록을 불러오지 못했습니다. {state.error.message}</InlineNotice>
      )}

      {state.status === 'success' &&
        (state.data.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white py-16 text-center">
            <p className="text-[15px] font-medium text-slate-600">아직 진행한 면접이 없습니다.</p>
            <p className="mt-1 text-[13px] text-slate-400">새 면접을 시작하고 답변에 대한 AI 피드백을 받아 보세요.</p>
            <button
              onClick={() => navigate('/interviews/new')}
              className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
              type="button"
            >
              + 새 면접 시작
            </button>
          </div>
        ) : (
          <ul className="divide-y divide-slate-100 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            {state.data.map((interview) => (
              <ListRow
                key={interview.id}
                interview={interview}
                confirming={confirmingId === interview.id}
                onOpen={() => navigate(`/interviews/${interview.id}`)}
                onAskDelete={() => setConfirmingId(interview.id)}
                onCancelDelete={() => setConfirmingId(null)}
                onConfirmDelete={() => remove(interview.id)}
              />
            ))}
          </ul>
        ))}
    </div>
  );
}

function ListRow({
  interview,
  confirming,
  onOpen,
  onAskDelete,
  onCancelDelete,
  onConfirmDelete,
}: {
  interview: InterviewSummary;
  confirming: boolean;
  onOpen: () => void;
  onAskDelete: () => void;
  onCancelDelete: () => void;
  onConfirmDelete: () => void;
}) {
  return (
    <li className="flex items-center pr-3">
      <button
        onClick={onOpen}
        className="flex min-w-0 flex-1 items-center gap-4 px-5 py-4 text-left transition hover:bg-slate-50"
        type="button"
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate font-semibold text-slate-900">{interview.targetCompany ?? '모의 면접'}</span>
            <span className="shrink-0 rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-medium text-blue-700">
              {TYPE_LABEL[interview.interviewType]}
            </span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[12px] text-slate-500">
            {interview.targetPosition && (
              <span className="rounded-md bg-slate-100 px-2 py-0.5 text-slate-600">{interview.targetPosition}</span>
            )}
            <span>· 문항 {interview.itemCount}개</span>
            <span>· {interview.createdAt}</span>
          </div>
        </div>
      </button>

      {confirming ? (
        <div className="flex shrink-0 items-center gap-1">
          <button
            onClick={onConfirmDelete}
            className="rounded-md bg-rose-500 px-2.5 py-1 text-[12px] font-semibold text-white hover:bg-rose-600"
            type="button"
          >
            삭제
          </button>
          <button
            onClick={onCancelDelete}
            className="rounded-md px-2 py-1 text-[12px] font-medium text-slate-500 hover:bg-slate-100"
            type="button"
          >
            취소
          </button>
        </div>
      ) : (
        <button
          onClick={onAskDelete}
          aria-label={`${interview.targetCompany ?? '모의 면접'} 삭제`}
          className="shrink-0 rounded-md p-2 text-slate-300 transition hover:bg-rose-50 hover:text-rose-500"
          type="button"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="size-4">
            <path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      )}
    </li>
  );
}

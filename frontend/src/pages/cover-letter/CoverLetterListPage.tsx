import { LoadingScreen } from '../../components/brand/LoadingScreen';
import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { InlineNotice } from '../../components/common/InlineNotice';
import { deleteCoverLetter } from '../../features/cover-letter/api';
import { useCoverLetters } from '../../features/cover-letter/queries';
import type { CoverLetterSummary } from '../../features/cover-letter/types';
import { useAuth } from '../../features/auth/AuthProvider';
import { CoverLetterHeader } from './CoverLetterHeader';

export function CoverLetterListPage() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50">
        <CoverLetterHeader />
        <LoadingScreen />
      </div>
    );
  }

  // 게스트는 목록이 없다 — 바로 작성 화면으로 보낸다.
  if (!user) return <Navigate replace to="/cover-letters/new" />;

  return (
    <div className="min-h-screen bg-slate-50">
      <CoverLetterHeader />
      <ListBody />
    </div>
  );
}

function ListBody() {
  const navigate = useNavigate();
  const { state, retry } = useCoverLetters();
  const [confirmingId, setConfirmingId] = useState<number | null>(null);

  const remove = async (id: number) => {
    setConfirmingId(null);
    await deleteCoverLetter(id);
    retry();
  };

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-950">내 자기소개서</h1>
          <p className="mt-1 text-sm text-slate-500">
            자소서를 선택해 문항과 답변을 수정할 수 있어요.
          </p>
        </div>
        <button
          onClick={() => navigate('/cover-letters/new', { state: { fresh: true } })}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700"
          type="button"
        >
          + 새 자소서
        </button>
      </div>

      {state.status === 'loading' && (
        <div className="rounded-2xl border border-slate-200 bg-white">
          <LoadingScreen compact message="자소서를 불러오는 중" />
        </div>
      )}

      {state.status === 'error' && (
        <InlineNotice onRetry={retry}>목록을 불러오지 못했습니다. {state.error.message}</InlineNotice>
      )}

      {state.status === 'success' &&
        (state.data.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white py-16 text-center">
            <p className="text-[15px] font-medium text-slate-600">아직 저장된 자소서가 없습니다.</p>
            <p className="mt-1 text-[13px] text-slate-400">채용공고 주소를 넣으면 지원 회사와 직무를 대신 채워 드려요.</p>
            <button
              onClick={() => navigate('/cover-letters/new', { state: { fresh: true } })}
              className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
              type="button"
            >
              + 새 자소서 작성
            </button>
          </div>
        ) : (
          <ul className="divide-y divide-slate-100 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            {state.data.map((letter) => (
              <ListRow
                key={letter.id}
                letter={letter}
                confirming={confirmingId === letter.id}
                onOpen={() => navigate(`/cover-letters/${letter.id}`)}
                onAskDelete={() => setConfirmingId(letter.id)}
                onCancelDelete={() => setConfirmingId(null)}
                onConfirmDelete={() => remove(letter.id)}
              />
            ))}
          </ul>
        ))}
    </div>
  );
}

function ListRow({
  letter,
  confirming,
  onOpen,
  onAskDelete,
  onCancelDelete,
  onConfirmDelete,
}: {
  letter: CoverLetterSummary;
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
            <span className="truncate font-semibold text-slate-900">{letter.title}</span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[12px] text-slate-500">
            {letter.targetCompany && (
              <span className="rounded-md bg-blue-50 px-2 py-0.5 text-blue-600">{letter.targetCompany}</span>
            )}
            {letter.targetPosition && (
              <span className="rounded-md bg-slate-100 px-2 py-0.5 text-slate-600">{letter.targetPosition}</span>
            )}
            <span>· 문항 {letter.itemCount}개</span>
            <span>· 수정일 {letter.updatedAt}</span>
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
          aria-label={`${letter.title} 삭제`}
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

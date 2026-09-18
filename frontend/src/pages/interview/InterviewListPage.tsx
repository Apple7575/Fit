import { useEffect, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { LoadingScreen } from '../../components/brand/LoadingScreen';
import { InlineNotice } from '../../components/common/InlineNotice';
import { useAuth } from '../../features/auth/AuthProvider';
import { CompanyLogo } from '../../features/company-summary/CompanyLogo';
import { deleteInterview } from '../../features/interview/api';
import { Icon } from '../../features/interview/icons';
import { deleteByServerId, listServerIdsWithClips } from '../../features/interview/localVideo';
import { useInterviews } from '../../features/interview/queries';
import { CARD, T } from '../../features/interview/reportTokens';
import { TYPE_ACCENT, TYPE_LABEL } from '../../features/interview/styles';
import type { InterviewSummary } from '../../features/interview/types';
import { useCompanyBrand } from '../../features/interview/useCompanyBrand';
import { formatDateDots } from '../../utils/formatDate';
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
  const [localIds, setLocalIds] = useState<Set<number>>(new Set());

  // 이 브라우저에 녹화가 남아 있는 면접을 표시하기 위해 한 번 로드한다.
  useEffect(() => {
    let cancelled = false;
    listServerIdsWithClips()
      .then((ids) => {
        if (!cancelled) setLocalIds(ids);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const remove = async (id: number) => {
    setConfirmingId(null);
    await deleteInterview(id);
    // 서버 기록을 지우면 이 브라우저의 로컬 녹화도 함께 정리한다.
    await deleteByServerId(id).catch(() => {});
    setLocalIds((prev) => {
      if (!prev.has(id)) return prev;
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
    retry();
  };

  return (
    // 리포트·면접 화면과 같은 폭을 쓴다
    <div className="mx-auto max-w-[1320px] px-5 py-6 lg:px-8">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-extrabold text-slate-950">내 모의 면접</h1>
          <p className={`mt-1 ${T.caption}`}>면접을 선택해 결과를 다시 보거나, 새 면접을 시작하세요. 결과는 나에게만 보입니다.</p>
        </div>
        <button
          className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-[13px] font-semibold text-white shadow-sm transition hover:bg-blue-700"
          onClick={() => navigate('/interviews/new')}
          type="button"
        >
          <Icon name="mic" />새 면접
        </button>
      </div>

      {state.status === 'loading' && (
        <div className={CARD}>
          <LoadingScreen compact message="면접 기록을 불러오는 중" />
        </div>
      )}

      {state.status === 'error' && (
        <InlineNotice onRetry={retry}>목록을 불러오지 못했습니다. {state.error.message}</InlineNotice>
      )}

      {state.status === 'success' &&
        (state.data.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white py-16 text-center">
            <p className={T.bodyStrong}>아직 진행한 면접이 없습니다.</p>
            <p className={`mt-1 ${T.caption}`}>새 면접을 시작하고 답변에 대한 AI 피드백을 받아 보세요.</p>
            <button
              className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-[13px] font-semibold text-white transition hover:bg-blue-700"
              onClick={() => navigate('/interviews/new')}
              type="button"
            >
              첫 면접 시작하기
            </button>
          </div>
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {state.data.map((interview) => (
              <InterviewCard
                confirming={confirmingId === interview.id}
                hasLocal={localIds.has(interview.id)}
                interview={interview}
                key={interview.id}
                onAskDelete={() => setConfirmingId(interview.id)}
                onCancelDelete={() => setConfirmingId(null)}
                onConfirmDelete={() => void remove(interview.id)}
                onOpen={() => navigate(`/interviews/${interview.id}`)}
              />
            ))}
          </ul>
        ))}
    </div>
  );
}

/**
 * 면접 한 건 카드. 카드 전체가 열기 버튼이고 삭제만 그 위에 따로 올린다(버튼 중첩을 피한다).
 * 유형은 배경 대신 위쪽 띠·배지·머리글자 색으로만 구분한다.
 */
function InterviewCard({
  interview,
  hasLocal,
  confirming,
  onOpen,
  onAskDelete,
  onCancelDelete,
  onConfirmDelete,
}: {
  interview: InterviewSummary;
  hasLocal: boolean;
  confirming: boolean;
  onOpen: () => void;
  onAskDelete: () => void;
  onCancelDelete: () => void;
  onConfirmDelete: () => void;
}) {
  const accent = TYPE_ACCENT[interview.interviewType];
  const company = interview.targetCompany ?? '모의 면접';
  const brand = useCompanyBrand(interview.targetCompany);

  return (
    <li className="group relative">
      {/* 카드 전체가 버튼이라 안쪽은 전부 span 으로 둔다 (버튼 안에 블록 요소를 넣지 않는다) */}
      <button
        className="block w-full overflow-hidden rounded-2xl border border-slate-200 bg-white text-left shadow-sm transition duration-150 hover:-translate-y-1 hover:border-blue-300 hover:shadow-lg focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:outline-none active:translate-y-0 active:shadow-sm"
        onClick={onOpen}
        type="button"
      >
        <span aria-hidden="true" className={`block h-1 w-full ${accent.strip}`} />

        <span className="block p-5 pr-12">
          <span className="flex items-center gap-3">
            <CompanyLogo
              className="rounded-xl"
              corpCode={brand?.corpCode ?? company}
              corpName={company}
              homepageUrl={brand?.homepageUrl ?? null}
              size={40}
            />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[17px] font-extrabold text-slate-950">{company}</span>
              <span className={`block truncate ${T.caption}`}>{interview.targetPosition ?? '직무 미지정'}</span>
            </span>
          </span>

          <span className="mt-4 flex flex-wrap items-center gap-1.5">
            <span className={`rounded-full px-2 py-0.5 text-[12px] font-semibold ring-1 ${accent.chip}`}>
              {TYPE_LABEL[interview.interviewType]}
            </span>
            <span className="rounded-full bg-slate-50 px-2 py-0.5 text-[12px] font-semibold text-slate-500 ring-1 ring-slate-200">
              문항 {interview.itemCount}개
            </span>
            {hasLocal && (
              <span className="flex items-center gap-1 rounded-full bg-slate-50 px-2 py-0.5 text-[12px] font-semibold text-slate-500 ring-1 ring-slate-200">
                <Icon className="size-3.5" name="frame" />
                녹화 있음
              </span>
            )}
          </span>

          {interview.overallSummary && (
            <span className={`mt-3 line-clamp-2 ${T.body}`}>{interview.overallSummary}</span>
          )}

          {/* 눌러서 열 수 있는 카드라는 걸 알려 주는 자리 */}
          <span className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3">
            <span className={T.caption}>{formatDateDots(interview.createdAt)}</span>
            <span className="flex items-center gap-1 text-[12px] font-semibold text-slate-400 transition group-hover:text-blue-600">
              결과 보기
              <Icon className="size-4 transition-transform group-hover:translate-x-0.5" name="next" />
            </span>
          </span>
        </span>
      </button>

      {confirming ? (
        <div className="absolute right-3 top-4 flex items-center gap-1">
          <button
            className="rounded-md bg-red-500 px-2.5 py-1 text-[12px] font-semibold text-white transition hover:bg-red-600"
            onClick={onConfirmDelete}
            type="button"
          >
            삭제
          </button>
          <button
            className="rounded-md px-2 py-1 text-[12px] font-semibold text-slate-500 transition hover:bg-slate-100"
            onClick={onCancelDelete}
            type="button"
          >
            취소
          </button>
        </div>
      ) : (
        <button
          aria-label={`${company} 삭제`}
          className="absolute right-3 top-4 rounded-md p-2 text-slate-300 transition hover:bg-red-50 hover:text-red-500"
          onClick={onAskDelete}
          type="button"
        >
          <svg className="size-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
            <path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      )}
    </li>
  );
}

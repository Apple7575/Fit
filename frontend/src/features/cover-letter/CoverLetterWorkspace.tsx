import { useState } from 'react';
import { ApiError } from '../../api/client';
import { AnnotatedAnswer } from './AnnotatedAnswer';
import { CommentCard } from './CommentCard';
import { CompanyPicker } from './CompanyPicker';
import { requestFeedback } from './api';
import type { CoverLetterInput, FeedbackComment } from './types';

interface CoverLetterWorkspaceProps {
  initial: CoverLetterInput;
  isLoggedIn: boolean;
  alreadySaved?: boolean;
  onSave: (input: CoverLetterInput) => Promise<void>;
  onBack?: () => void;
}

type Status = 'idle' | 'running' | 'done' | 'error';

interface WorkItem {
  key: string;
  question: string;
  answer: string;
  charLimit: number;
  editing: boolean;
  status: Status;
  stale: boolean;
  errorMessage?: string;
  summary?: string;
  comments: FeedbackComment[];
}

const uid = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`);

const toWorkItem = (item: CoverLetterInput['items'][number]): WorkItem => ({
  key: uid(),
  question: item.question,
  answer: item.answer,
  charLimit: item.charLimit,
  editing: item.question.trim() === '',
  status: item.feedback ? 'done' : 'idle',
  stale: false,
  summary: item.feedback?.summary,
  comments: item.feedback?.comments ?? [],
});

export function CoverLetterWorkspace({
  initial,
  isLoggedIn,
  alreadySaved,
  onSave,
  onBack,
}: CoverLetterWorkspaceProps) {
  const [title, setTitle] = useState(initial.title);
  const [company, setCompany] = useState(initial.targetCompany ?? '');
  const [position, setPosition] = useState(initial.targetPosition ?? '');
  const [items, setItems] = useState<WorkItem[]>(() => initial.items.map(toWorkItem));
  const [activeKey, setActiveKey] = useState<string | null>(null);

  // 본문 quote 클릭 시에만 해당 코멘트로 이동한다(hover 로는 강조만).
  const scrollToComment = (key: string) => {
    setActiveKey(key);
    document.getElementById(`cl-comment-${key}`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  };
  const [dirty, setDirty] = useState(false);
  const [savedOnce, setSavedOnce] = useState(alreadySaved ?? false);
  const [saving, setSaving] = useState(false);

  const touch = () => setDirty(true);
  const patch = (key: string, next: Partial<WorkItem>) =>
    setItems((prev) => prev.map((item) => (item.key === key ? { ...item, ...next } : item)));

  const editItem = (key: string, next: Partial<WorkItem>) => {
    setItems((prev) =>
      prev.map((item) =>
        item.key === key ? { ...item, ...next, stale: item.status === 'done' ? true : item.stale } : item,
      ),
    );
    touch();
  };

  const addItem = () => {
    setItems((prev) => [
      ...prev,
      {
        key: uid(),
        question: '',
        answer: '',
        charLimit: 500,
        editing: true,
        status: 'idle',
        stale: false,
        comments: [],
      },
    ]);
    touch();
  };

  const removeItem = (key: string) => {
    if (items.length <= 1) return;
    setItems((prev) => prev.filter((item) => item.key !== key));
    touch();
  };

  const runFeedback = async (item: WorkItem) => {
    patch(item.key, { status: 'running', editing: false, errorMessage: undefined });
    try {
      const feedback = await requestFeedback({
        question: item.question,
        answer: item.answer,
        charLimit: item.charLimit,
        targetPosition: position.trim() || null,
      });
      patch(item.key, {
        status: 'done',
        stale: false,
        summary: feedback.summary,
        comments: feedback.comments,
      });
      touch();
    } catch (error) {
      patch(item.key, {
        status: 'error',
        errorMessage: error instanceof ApiError ? error.message : 'AI 피드백에 실패했습니다.',
      });
    }
  };

  const buildInput = (): CoverLetterInput => ({
    title: title.trim() || '제목 없는 자소서',
    targetCompany: company.trim() || null,
    targetPosition: position.trim() || null,
    items: items.map((item) => ({
      question: item.question,
      answer: item.answer,
      charLimit: item.charLimit,
      feedback:
        item.status === 'done'
          ? { summary: item.summary ?? '', model: 'gemini-2.5-flash', comments: item.comments }
          : null,
    })),
  });

  const save = async () => {
    setSaving(true);
    try {
      await onSave(buildInput());
      setDirty(false);
      setSavedOnce(true);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      {onBack && (
        <button onClick={onBack} className="mb-4 text-sm text-slate-500 hover:text-slate-800" type="button">
          ← 목록으로
        </button>
      )}

      {!isLoggedIn && (
        <div className="mb-5 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-xl border border-blue-100 bg-blue-50/70 px-4 py-3 text-[13px] text-slate-600">
          <span aria-hidden>✨</span>
          <span>
            <b className="font-semibold text-slate-800">로그인 없이</b> 자기소개서 AI 피드백을 받아볼 수
            있어요. 작성한 자소서와 피드백을 <b className="font-semibold text-slate-800">저장</b>하려면
            로그인하세요.
          </span>
        </div>
      )}

      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <input
            value={title}
            onChange={(event) => {
              setTitle(event.target.value);
              touch();
            }}
            placeholder="제목을 입력하세요 (예: 2026 상반기 백엔드 신입 지원)"
            className="w-full rounded-lg border border-transparent bg-transparent text-2xl font-bold tracking-tight text-slate-950 placeholder:text-slate-300 focus:border-slate-300 focus:bg-white focus:px-3 focus:py-1 focus:outline-none"
          />
          <p className="mt-1 text-sm text-slate-500">
            문항을 추가·삭제하고 답변을 수정한 뒤, 각 문항에서 AI 피드백을 받아보세요.
          </p>
        </div>
        <SaveArea
          isLoggedIn={isLoggedIn}
          dirty={dirty}
          savedOnce={savedOnce}
          saving={saving}
          onSave={save}
        />
      </div>

      <div className="mb-6 grid gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-[12px] font-medium text-slate-500">지원 회사 (선택)</label>
          <CompanyPicker
            value={company}
            onChange={(next) => {
              setCompany(next);
              touch();
            }}
          />
        </div>
        <div>
          <label className="mb-1 block text-[12px] font-medium text-slate-500">지원 직무 (선택)</label>
          <input
            value={position}
            onChange={(event) => {
              setPosition(event.target.value);
              touch();
            }}
            placeholder="예: 백엔드 개발"
            className="h-[42px] w-full rounded-lg border border-slate-200 px-3 text-[15px] text-slate-800 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
          />
        </div>
      </div>

      <div className="space-y-6">
        {items.map((item, index) => (
          <section
            key={item.key}
            className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
          >
            <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 bg-slate-50 px-5 py-3">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-600 text-[12px] font-semibold text-white">
                {index + 1}
              </span>
              <span className="text-[14px] font-medium text-slate-700">
                {item.editing ? `문항 ${index + 1} 편집` : item.question || '(질문 미입력)'}
              </span>

              <div className="ml-auto flex items-center gap-2">
                <button
                  onClick={() => patch(item.key, { editing: !item.editing })}
                  className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[13px] font-medium text-slate-600 hover:bg-slate-100"
                  type="button"
                >
                  {item.editing ? '완료' : '수정'}
                </button>
                {items.length > 1 && (
                  <button
                    onClick={() => removeItem(item.key)}
                    className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[13px] font-medium text-slate-500 hover:bg-rose-50 hover:text-rose-600"
                    type="button"
                  >
                    삭제
                  </button>
                )}
                <FeedbackButton status={item.status} stale={item.stale} onClick={() => runFeedback(item)} />
              </div>
            </div>

            <div className="grid gap-0 lg:grid-cols-[1.4fr_1fr]">
              <div className="border-slate-100 p-5 lg:border-r">
                {item.editing ? (
                  <div className="space-y-3">
                    <div className="flex flex-col gap-3 sm:flex-row">
                      <div className="flex-1">
                        <label className="mb-1 block text-[12px] font-medium text-slate-500">질문</label>
                        <input
                          value={item.question}
                          onChange={(event) => editItem(item.key, { question: event.target.value })}
                          placeholder="예: 지원 동기와 입사 후 포부를 기술하시오."
                          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-[14px] text-slate-800 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
                        />
                      </div>
                      <div className="sm:w-32">
                        <label className="mb-1 block text-[12px] font-medium text-slate-500">글자 수 제한</label>
                        <input
                          type="number"
                          min={1}
                          max={4000}
                          value={item.charLimit}
                          onChange={(event) =>
                            editItem(item.key, { charLimit: Math.min(4000, Number(event.target.value) || 0) })
                          }
                          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-[14px] text-slate-800 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="mb-1 block text-[12px] font-medium text-slate-500">답변</label>
                      <textarea
                        value={item.answer}
                        onChange={(event) => editItem(item.key, { answer: event.target.value })}
                        rows={5}
                        maxLength={item.charLimit || 4000}
                        placeholder="답변을 붙여넣거나 입력하세요."
                        className="w-full resize-y rounded-lg border border-slate-200 p-3 text-[15px] leading-7 text-slate-700 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
                      />
                      <div className="mt-1.5 text-right text-[12px] text-slate-400">
                        <span className={item.answer.length > item.charLimit ? 'text-rose-500' : ''}>
                          {item.answer.length}
                        </span>{' '}
                        / {item.charLimit}자
                      </div>
                    </div>
                  </div>
                ) : (
                  <AnnotatedAnswer
                    itemKey={item.key}
                    answer={item.answer}
                    comments={item.status === 'done' ? item.comments : []}
                    activeKey={activeKey}
                    onHover={setActiveKey}
                    onSelect={scrollToComment}
                  />
                )}
              </div>

              <div className="space-y-3 bg-slate-50/50 p-4">
                <CommentColumn
                  item={item}
                  activeKey={activeKey}
                  onHover={setActiveKey}
                  onRetry={() => runFeedback(item)}
                />
              </div>
            </div>
          </section>
        ))}
      </div>

      <button
        onClick={addItem}
        className="mt-4 w-full rounded-lg border border-dashed border-slate-300 py-2.5 text-sm text-slate-500 hover:bg-slate-50"
        type="button"
      >
        + 문항 추가
      </button>
    </div>
  );
}

function SaveArea({
  isLoggedIn,
  dirty,
  savedOnce,
  saving,
  onSave,
}: {
  isLoggedIn: boolean;
  dirty: boolean;
  savedOnce: boolean;
  saving: boolean;
  onSave: () => void;
}) {
  if (!isLoggedIn) {
    return (
      <div className="text-right">
        <button
          onClick={onSave}
          disabled={saving}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold text-white shadow-sm transition hover:bg-blue-700 disabled:bg-slate-300"
          type="button"
        >
          {saving ? '이동 중…' : '로그인하고 저장'}
        </button>
        <p className="mt-1 text-[11.5px] text-slate-400">저장하려면 로그인이 필요해요</p>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      {savedOnce && !dirty && <span className="text-[12.5px] font-medium text-emerald-600">저장됨 ✓</span>}
      <button
        onClick={onSave}
        disabled={saving || (savedOnce && !dirty)}
        className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        type="button"
      >
        {saving ? '저장 중…' : '저장'}
      </button>
    </div>
  );
}

function FeedbackButton({
  status,
  stale,
  onClick,
}: {
  status: Status;
  stale: boolean;
  onClick: () => void;
}) {
  if (status === 'running') {
    return (
      <span className="flex items-center gap-2 rounded-lg bg-blue-100 px-3 py-1.5 text-[13px] font-medium text-blue-500">
        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-blue-300 border-t-blue-600" />
        분석 중…
      </span>
    );
  }
  if (status === 'done') {
    return (
      <button
        onClick={onClick}
        className={[
          'rounded-lg border px-3 py-1.5 text-[13px] font-medium',
          stale
            ? 'border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100'
            : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-100',
        ].join(' ')}
        type="button"
      >
        ↻ 다시 받기
      </button>
    );
  }
  return (
    <button
      onClick={onClick}
      className="rounded-lg bg-blue-600 px-3 py-1.5 text-[13px] font-semibold text-white hover:bg-blue-700"
      type="button"
    >
      ✨ AI 피드백
    </button>
  );
}

function CommentColumn({
  item,
  activeKey,
  onHover,
  onRetry,
}: {
  item: WorkItem;
  activeKey: string | null;
  onHover: (key: string | null) => void;
  onRetry: () => void;
}) {
  if (item.status === 'running') {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-center">
        <div className="mb-3 h-7 w-7 animate-spin rounded-full border-4 border-slate-200 border-t-blue-500" />
        <p className="text-[13px] text-slate-500">이 문항을 분석하고 있어요…</p>
      </div>
    );
  }

  if (item.status === 'error') {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 py-10 text-center">
        <p className="text-[13px] text-amber-700">{item.errorMessage}</p>
        <button
          onClick={onRetry}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-[13px] font-medium text-slate-700 hover:bg-slate-100"
          type="button"
        >
          다시 시도
        </button>
      </div>
    );
  }

  if (item.status === 'idle') {
    return (
      <div className="flex h-full flex-col items-center justify-center py-10 text-center">
        <p className="text-[13px] text-slate-400">아직 피드백이 없습니다.</p>
        <p className="mt-0.5 text-[13px] text-slate-400">
          위 <span className="font-medium text-blue-500">AI 피드백</span> 버튼을 눌러 피드백을 받아보세요.
        </p>
      </div>
    );
  }

  return (
    <>
      {item.stale && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-[12.5px] text-amber-700">
          내용이 수정되었습니다. <b>다시 받기</b>로 최신 피드백을 받아보세요.
        </div>
      )}
      {item.summary && (
        <p className="rounded-lg bg-white px-3 py-2 text-[13px] leading-6 text-slate-600 shadow-sm">
          {item.summary}
        </p>
      )}
      {item.comments.length === 0 ? (
        <p className="py-6 text-center text-[13px] text-slate-400">특별한 지적 없이 잘 작성되었습니다. 👍</p>
      ) : (
        item.comments.map((comment, index) => {
          const key = `${item.key}#${index}`;
          return (
            <CommentCard
              key={key}
              commentKey={key}
              comment={comment}
              active={activeKey === key}
              onHover={(active) => onHover(active ? key : null)}
            />
          );
        })
      )}
    </>
  );
}

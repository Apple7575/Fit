import { useState } from 'react';
import { ApiError, isRateLimited } from '../../api/client';
import { CompanyPicker } from './CompanyPicker';
import { parseJobPosting, registerJobPosting } from './api';
import type { CoverLetterInput, PendingJobPosting } from './types';

interface CoverLetterWorkspaceProps {
  initial: CoverLetterInput;
  isLoggedIn: boolean;
  alreadySaved?: boolean;
  /** 방금 저장하고 들어온 화면. 새 자소서를 저장하면 주소가 갈리므로 그때 이어서 알린다. */
  justSaved?: boolean;
  /**
   * 자소서만 저장한다. 아직 등록하지 않은 공고가 있으면 두 번째 인자로 함께 넘긴다 —
   * 등록이 수십 초 걸려 저장을 붙잡아 둘 수 없으니, 화면을 넘긴 뒤에 받는 쪽에서 잇는다.
   */
  onSave: (input: CoverLetterInput, pendingPosting: PendingJobPosting | null) => Promise<void>;
  /** 저장한 뒤 멀티에이전트 검토 화면으로 넘긴다. 방은 저장된 자소서에 붙기 때문이다. */
  onReview: (input: CoverLetterInput) => Promise<void>;
  onBack?: () => void;
}

interface WorkItem {
  key: string;
  question: string;
  answer: string;
  charLimit: number;
}

const uid = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`);

/** 공고를 어떤 회사·직무로 등록했는지 적어 두는 열쇠. 달라지면 등록한 공고가 더는 맞지 않는다. */
const postingKey = (company?: string | null, position?: string | null) =>
  `${(company ?? '').trim()}|${(position ?? '').trim()}`;

const toWorkItem = (item: CoverLetterInput['items'][number]): WorkItem => ({
  key: uid(),
  question: item.question,
  answer: item.answer,
  charLimit: item.charLimit,
});

export function CoverLetterWorkspace({
  initial,
  isLoggedIn,
  alreadySaved,
  justSaved,
  onSave,
  onReview,
  onBack,
}: CoverLetterWorkspaceProps) {
  const [title, setTitle] = useState(initial.title);
  const [company, setCompany] = useState(initial.targetCompany ?? '');
  const [position, setPosition] = useState(initial.targetPosition ?? '');
  // 공고에 직무가 여럿이면 여기 담아 두고 고르게 한다. 하나뿐이면 바로 채우고 비워 둔다.
  const [positionChoices, setPositionChoices] = useState<string[]>([]);
  // 목록에 없는 직무를 쓰려는 경우. 고른 목록을 버리지 않고 입력칸만 바꿔 준다.
  const [typingPosition, setTypingPosition] = useState(false);
  const [items, setItems] = useState<WorkItem[]>(() => initial.items.map(toWorkItem));
  const [dirty, setDirty] = useState(false);
  const [savedOnce, setSavedOnce] = useState(alreadySaved ?? false);
  // 방금 저장했다는 알림. 다시 고치기 시작하면 사실이 아니게 되므로 그때 내린다.
  const [justSavedNotice, setJustSavedNotice] = useState(justSaved ?? false);
  const [saving, setSaving] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  // 확인만 해 둔 공고. 이 주소로 등록한다.
  const [posting, setPosting] = useState<PendingJobPosting | null>(null);
  // 등록해 둔 공고와, 그때의 회사·직무. 그 뒤에 회사나 직무를 바꾸면 다시 등록해야 한다.
  const [registered, setRegistered] = useState<{ id: string; of: string } | null>(() =>
    initial.jobContextId
      ? { id: initial.jobContextId, of: postingKey(initial.targetCompany, initial.targetPosition) }
      : null,
  );
  const [registering, setRegistering] = useState(false);

  const touch = () => {
    setDirty(true);
    setJustSavedNotice(false);
  };

  const editItem = (key: string, next: Partial<WorkItem>) => {
    setItems((prev) => prev.map((item) => (item.key === key ? { ...item, ...next } : item)));
    touch();
  };

  const addItem = () => {
    setItems((prev) => [...prev, { key: uid(), question: '', answer: '', charLimit: 500 }]);
    touch();
  };

  const removeItem = (key: string) => {
    if (items.length <= 1) return;
    setItems((prev) => prev.filter((item) => item.key !== key));
    touch();
  };

  // 공고에서 읽어 온 값은 저장되지 않는다. 입력칸을 채울 뿐이라 여기서도 미저장 표시를 켠다.
  const applyPosting = (
    companyName: string | null,
    positions: string[],
    sourceUrl: string,
    sourceKey: string | null,
  ) => {
    // 주소만 들고 있다가 저장할 때 등록한다. 지금 등록하면 그 뒤에 직무를 바꿨을 때 어긋난다.
    setPosting({ url: sourceUrl, sourceKey });
    setRegistered(null);
    if (companyName) setCompany(companyName);
    setTypingPosition(false);
    if (positions.length === 1) {
      // 한 직무만 뽑는 공고면 고를 것이 없다. 회사처럼 바로 채운다.
      setPosition(positions[0]);
      setPositionChoices([]);
    } else {
      // 여럿이면 고르기 전까지 비워 둔다. 첫 직무를 멋대로 넣으면 고른 줄 안다.
      setPositionChoices(positions);
      if (positions.length > 1) setPosition('');
    }
    touch();
  };

  const buildInput = (): CoverLetterInput => ({
    title: title.trim() || '제목 없는 자소서',
    targetCompany: company.trim() || null,
    targetPosition: position.trim() || null,
    jobContextId: registered?.id ?? null,
    items: items.map((item) => ({
      question: item.question,
      answer: item.answer,
      charLimit: item.charLimit,
    })),
  });

  /** 아직 등록하지 않은 공고. 같은 회사·직무로 이미 등록해 뒀으면 등록할 것이 없다. */
  const postingToRegister = (base: CoverLetterInput): PendingJobPosting | null => {
    const key = postingKey(base.targetCompany, base.targetPosition);
    return !posting || registered?.of === key ? null : posting;
  };

  /**
   * 검토 직전에 공고를 등록해 식별자를 붙인다. 검토 방은 자소서에 적힌 이 값을 물려받는다.
   *
   * 등록은 모델이 공고를 요구사항 단위로 정리하므로 수십 초 걸린다. 그동안 검토 버튼이
   * "공고 분석 중…" 으로 남는다. 검토는 이 값이 있어야 제 일을 하므로 기다린다.
   *
   * 실패해도 검토는 그대로 연다. 공고는 선택 항목이라 써 둔 글을 못 보게 할 이유가 없다.
   */
  const inputForReview = async (): Promise<CoverLetterInput> => {
    const base = buildInput();
    const pending = postingToRegister(base);
    if (!pending) {
      return base;
    }

    setRegistering(true);
    try {
      const context = await registerJobPosting(
        pending.url,
        base.targetCompany ?? null,
        base.targetPosition ?? null,
        pending.sourceKey,
      );
      setRegistered({
        id: context.jobContextId,
        of: postingKey(base.targetCompany, base.targetPosition),
      });
      return { ...base, jobContextId: context.jobContextId };
    } catch {
      return { ...base, jobContextId: null };
    } finally {
      setRegistering(false);
    }
  };

  /** 저장은 공고 등록을 기다리지 않는다. 자소서를 먼저 넘기고 등록은 받는 쪽이 뒤에서 잇는다. */
  const save = async () => {
    setSaving(true);
    try {
      const base = buildInput();
      await onSave(base, postingToRegister(base));
      setDirty(false);
      setSavedOnce(true);
      setJustSavedNotice(true);
    } finally {
      setSaving(false);
    }
  };

  const review = async () => {
    setReviewing(true);
    try {
      await onReview(await inputForReview());
    } finally {
      setReviewing(false);
    }
  };

  // 질문과 답변이 다 빈 자소서를 검토에 넘기면 에이전트가 볼 것이 없다.
  const hasWriting = items.some((item) => item.question.trim() !== '' && item.answer.trim() !== '');

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      {onBack && (
        <button onClick={onBack} className="mb-4 text-sm text-slate-500 hover:text-slate-800" type="button">
          ← 목록으로
        </button>
      )}

      {!isLoggedIn && (
        <div className="mb-5 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-xl border border-blue-100 bg-blue-50/70 px-4 py-3 text-[13px] text-slate-600">
          <span aria-hidden>✨</span>
          <span>
            작성한 자기소개서를 <b className="font-semibold text-slate-800">저장</b>하려면 로그인하세요.
          </span>
        </div>
      )}

      <div className="mb-5">
        <label className="mb-1 block text-[12px] font-medium text-slate-500" htmlFor="cl-title">
          제목
        </label>
        {/* 테두리를 늘 보여준다. 눌러야 박스가 나타나면 고칠 수 있는 칸인 줄 모른다. */}
        <input
          id="cl-title"
          value={title}
          onChange={(event) => {
            setTitle(event.target.value);
            touch();
          }}
          placeholder="제목을 입력하세요 (예: 2026 상반기 백엔드 신입 지원)"
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-2xl font-bold tracking-tight text-slate-950 placeholder:text-[17px] placeholder:font-normal placeholder:text-slate-300 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
        />
        <p className="mt-1.5 text-sm text-slate-500">문항을 추가·삭제하고 답변을 수정한 뒤 저장하세요.</p>
      </div>

      <JobPostingBar onParsed={applyPosting} />

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
          <label className="mb-1 block text-[12px] font-medium text-slate-500" htmlFor="cl-position">
            지원 직무 (선택)
          </label>
          {positionChoices.length > 1 && !typingPosition ? (
            <PositionSelect
              choices={positionChoices}
              selected={position}
              onSelect={(next) => {
                setPosition(next);
                touch();
              }}
              onTypeInstead={() => {
                setTypingPosition(true);
                setPosition('');
                touch();
              }}
            />
          ) : (
            <>
              <input
                id="cl-position"
                value={position}
                onChange={(event) => {
                  setPosition(event.target.value);
                  touch();
                }}
                placeholder="예: 백엔드 개발"
                className="h-[42px] w-full rounded-lg border border-slate-200 px-3 text-[15px] text-slate-800 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
              />
              {typingPosition && (
                <button
                  onClick={() => setTypingPosition(false)}
                  className="mt-1 text-[12px] font-medium text-blue-600 hover:text-blue-700"
                  type="button"
                >
                  공고에서 찾은 직무로 고르기
                </button>
              )}
            </>
          )}
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
              <span className="text-[14px] font-medium text-slate-700">문항 {index + 1}</span>

              {items.length > 1 && (
                <button
                  onClick={() => removeItem(item.key)}
                  className="ml-auto rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[13px] font-medium text-slate-500 hover:bg-rose-50 hover:text-rose-600"
                  type="button"
                >
                  삭제
                </button>
              )}
            </div>

            <div className="space-y-3 p-5">
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
                  rows={8}
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

      <div className="mt-6 flex flex-col items-end gap-1.5">
        <div className="flex items-center gap-2">
          <SaveArea
            isLoggedIn={isLoggedIn}
            dirty={dirty}
            savedOnce={savedOnce}
            saving={saving}
            registering={registering}
            justSaved={justSavedNotice}
            onSave={save}
          />
          <button
            onClick={review}
            disabled={reviewing || registering || !hasWriting}
            className="rounded-xl bg-slate-900 px-6 py-3 text-[15px] font-bold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
            type="button"
          >
            {registering ? '공고 분석 중…' : reviewing ? '여는 중…' : 'AI 검토'}
          </button>
        </div>
        <p className="text-[12px] text-slate-400">
          {!hasWriting
            ? '질문과 답변을 채우면 검토를 받을 수 있어요.'
            : isLoggedIn
              ? '저장한 뒤 에이전트 검토 화면으로 넘어가요.'
              : '검토를 받으려면 로그인이 필요해요.'}
        </p>
      </div>
    </div>
  );
}

type PostingStatus = 'idle' | 'loading' | 'done' | 'error';

/**
 * 채용공고 URL 을 넣고 확인하면 지원 회사와 직무를 대신 채워 준다.
 * 공고 내용은 저장하지 않는다 — 입력칸을 채우고 나면 버린다.
 */
function JobPostingBar({
  onParsed,
}: {
  onParsed: (
    companyName: string | null,
    positions: string[],
    sourceUrl: string,
    sourceKey: string | null,
  ) => void;
}) {
  const [url, setUrl] = useState('');
  const [status, setStatus] = useState<PostingStatus>('idle');
  const [message, setMessage] = useState('');
  // 자동 인식이 안 되는 것으로 판명난 URL. 같은 주소 재파싱은 성공하지 않으므로 다시 못 누르게 막는다.
  const [blockedUrl, setBlockedUrl] = useState<string | null>(null);

  const confirm = async () => {
    const target = url.trim();
    if (!target || target === blockedUrl) return;
    setStatus('loading');
    setMessage('');
    try {
      const result = await parseJobPosting(target);
      onParsed(result.companyName, result.positions, result.sourceUrl, result.sourceKey);
      // 잘 됐다는 말은 하지 않는다. 회사·직무 칸이 채워진 것으로 이미 보인다.
      setStatus('done');
      setMessage('');
    } catch (error) {
      setStatus('error');
      if (error instanceof ApiError && error.code === 'JOB_POSTING_PARSE_FAILED') {
        // 같은 URL 재시도는 무의미 → 그 주소를 잠그고 다른 주소/직접 입력으로 유도한다.
        setBlockedUrl(target);
        setMessage('이 공고는 자동 인식이 안 돼요. 다른 주소를 넣거나 회사·직무를 직접 입력해 주세요.');
      } else if (error instanceof ApiError && isRateLimited(error)) {
        setMessage('요청이 많습니다. 잠시 후 다시 시도해 주세요.');
      } else {
        setMessage(
          error instanceof ApiError
            ? error.message
            : '공고를 확인하지 못했습니다. 주소를 다시 확인해 주세요.',
        );
      }
    }
  };

  return (
    <div className="mb-6 rounded-xl border border-slate-200 bg-white p-4">
      <label className="mb-1 block text-[12px] font-medium text-slate-500" htmlFor="cl-posting-url">
        채용공고 URL (선택)
      </label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          id="cl-posting-url"
          value={url}
          onChange={(event) => {
            setUrl(event.target.value);
            if (status === 'error') {
              setStatus('idle');
              setMessage('');
            }
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              confirm();
            }
          }}
          type="url"
          inputMode="url"
          placeholder="공고 주소를 붙여넣으세요"
          className="h-[42px] min-w-0 flex-1 rounded-lg border border-slate-200 px-3 text-[15px] text-slate-800 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
        />
        <button
          onClick={confirm}
          disabled={status === 'loading' || url.trim() === '' || url.trim() === blockedUrl}
          className="h-[42px] shrink-0 rounded-lg bg-blue-600 px-5 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          type="button"
        >
          {status === 'loading' ? '확인 중…' : '확인'}
        </button>
      </div>

      <p
        className={[
          'mt-2 text-[12.5px]',
          status === 'error' ? 'text-amber-700' : 'text-slate-400',
        ].join(' ')}
        role={status === 'error' ? 'alert' : 'status'}
      >
        {message || '공고 주소를 넣고 확인하면 지원 회사와 직무를 대신 채워 드려요.'}
      </p>
    </div>
  );
}

/** 목록에 없는 직무를 쓰겠다는 뜻. 실제 직무명과 겹치지 않게 빈 값 쪽에 둔다. */
const TYPE_INSTEAD = '__type__';

/** 공고에서 직무를 여럿 뽑았을 때. 고르기 전까지는 빈 값이다. */
function PositionSelect({
  choices,
  selected,
  onSelect,
  onTypeInstead,
}: {
  choices: string[];
  selected: string;
  onSelect: (value: string) => void;
  onTypeInstead: () => void;
}) {
  return (
    <>
      <select
        id="cl-position"
        value={selected}
        onChange={(event) => {
          if (event.target.value === TYPE_INSTEAD) {
            onTypeInstead();
            return;
          }
          onSelect(event.target.value);
        }}
        className="h-[42px] w-full rounded-lg border border-slate-200 bg-white px-3 text-[15px] text-slate-800 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
      >
        <option value="">직무를 고르세요</option>
        {choices.map((choice) => (
          <option key={choice} value={choice}>
            {choice}
          </option>
        ))}
        <option value={TYPE_INSTEAD}>직접 입력</option>
      </select>
      <p className="mt-1 text-[12px] text-slate-400">공고에서 직무 {choices.length}개를 찾았어요.</p>
    </>
  );
}

function SaveArea({
  isLoggedIn,
  dirty,
  savedOnce,
  saving,
  registering,
  justSaved,
  onSave,
}: {
  isLoggedIn: boolean;
  dirty: boolean;
  savedOnce: boolean;
  saving: boolean;
  /** AI 검토가 공고를 등록하는 중. 저장과 겹치면 헛돌므로 그동안 잠가 둔다. */
  registering: boolean;
  /** 방금 저장했다. 열자마자 저장된 상태인 것(savedOnce)과 달리 사용자가 막 누른 결과다. */
  justSaved: boolean;
  onSave: () => void;
}) {
  // AI 검토 버튼과 나란히 서므로 크기를 맞춘다. 로그인 안내는 화면 위 배너가 이미 하고 있다.
  if (!isLoggedIn) {
    return (
      <button
        onClick={onSave}
        disabled={saving}
        className="rounded-xl bg-blue-600 px-6 py-3 text-[15px] font-bold text-white shadow-sm transition hover:bg-blue-700 disabled:bg-slate-300"
        type="button"
      >
        {saving ? '이동 중…' : '로그인하고 저장'}
      </button>
    );
  }

  return (
    <div className="flex items-center gap-2">
      {justSaved ? (
        <span role="status" className="text-[13px] font-semibold text-emerald-600">
          저장했습니다 ✓
        </span>
      ) : (
        savedOnce && !dirty && <span className="text-[12.5px] font-medium text-emerald-600">저장됨 ✓</span>
      )}
      <button
        onClick={onSave}
        disabled={saving || registering || (savedOnce && !dirty)}
        className="rounded-xl bg-blue-600 px-6 py-3 text-[15px] font-bold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        type="button"
      >
        {saving ? '저장 중…' : '저장'}
      </button>
    </div>
  );
}

import { useState } from 'react';
import { ApiError, isRateLimited } from '../../api/client';
import { userMessage } from '../../api/errorMessage';
import { Spinner } from '../../components/common/Spinner';
import { CompanyPicker } from './CompanyPicker';
import {
  UNTITLED_COVER_LETTER,
  parseJobPosting,
  parseJobPostingImages,
  registerJobPosting,
} from './api';
import {
  MAX_POSTING_IMAGES_BYTES,
  MAX_POSTING_IMAGE_BYTES,
  preparePostingImages,
} from './preparePostingImages';
import type { CoverLetterInput, PendingJobPosting } from './types';
import {
  MAX_ANSWER,
  MAX_POSITION,
  MAX_QUESTION,
  MAX_TITLE,
  findProblem,
  normalizeCharLimit,
} from './validate';

interface CoverLetterWorkspaceProps {
  initial: CoverLetterInput;
  initialPosting?: PendingJobPosting | null;
  isLoggedIn: boolean;
  alreadySaved?: boolean;
  /** 방금 저장하고 들어온 화면. 새 자소서를 저장하면 주소가 갈리므로 그때 이어서 알린다. */
  justSaved?: boolean;
  onSave: (input: CoverLetterInput, pendingPosting?: PendingJobPosting | null) => Promise<void>;
  /** 저장한 뒤 멀티에이전트 검토 화면으로 넘긴다. 방은 저장된 자소서에 붙기 때문이다. */
  onReview: (input: CoverLetterInput, pendingPosting?: PendingJobPosting | null) => Promise<void>;
  onBack?: () => void;
}

interface WorkItem {
  key: string;
  question: string;
  answer: string;
  /** 비어 있을 수 있다 — 지우는 도중에 1 로 되돌리면 글자를 지울 수가 없다 */
  charLimit: number | null;
}

/*
 * 첫 화면과 같은 영상을 쓴다. 원고를 넘기는 장면도 만들어 봤지만, 손과 종이가 글 쓰는
 * 칸 바로 뒤에서 크게 움직여 정신이 없었다. 배경은 눈에 띄면 안 된다.
 */
const HERO_VIDEO = '/cover-letter-media/hero.mp4';
const HERO_POSTER = '/cover-letter-media/hero.jpg';

const uid = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`);

/** 0 = 희망 기업·직무, 1 이상 = 그 번째 문항. 한 화면에 한 가지만 둔다. */
type Step = number;

const META_STEP = 0;

/** 문항은 최대 7개까지. 그 이상은 한 자소서로 다루기에 너무 길고, 검토도 늘어진다. */
const MAX_ITEMS = 7;

/**
 * 지금 어느 단계인지. 눌러서 아무 데나 오갈 수 있다 — 막아 두면 앞을 고치려다 길을 잃는다.
 *
 * <p>문항도 한 칸씩 차지한다. 예전에는 문항을 세로로 쌓고 맨 아래에 "문항 추가" 를 뒀는데,
 * 문항이 늘수록 줄줄이 스크롤해야 했고 지금 몇 번째를 쓰는지도 알기 어려웠다.
 */
function StepRail({
  step,
  filled,
  locked,
  atMax,
  onGo,
  onAdd,
}: {
  step: Step;
  /** 문항별로 질문·답변이 채워졌는지. 어디까지 썼는지 한눈에 보인다 */
  filled: boolean[];
  /** 앞 단계를 아직 안 채웠다. 문항으로 넘어갈 수 없다 */
  locked: boolean;
  /** 상한까지 다 썼다. 추가 알약이 사라진 까닭을 대신 적는다 */
  atMax: boolean;
  onGo: (next: Step) => void;
  /** 문항을 더한다. 첫 단계에서는 주지 않는다 — 제목도 없이 문항부터 열리면 안 된다 */
  onAdd?: () => void;
}) {
  const chip = (here: boolean) =>
    `flex items-center gap-2 rounded-full px-4 py-2 text-[13px] font-bold transition ${
      here ? 'bg-white text-slate-950' : 'text-white/60 ring-1 ring-white/20 hover:bg-white/10 hover:text-white'
    }`;

  return (
    <nav aria-label="작성 단계" className="mt-6 flex flex-wrap items-center gap-2">
      <button
        aria-current={step === META_STEP ? 'step' : undefined}
        className={chip(step === META_STEP)}
        onClick={() => onGo(META_STEP)}
        type="button"
      >
        희망 기업·직무
      </button>

      <span aria-hidden="true" className="text-white/25">→</span>

      {filled.map((done, index) => {
        const no = index + 1;
        const here = step === no;
        return (
          <button
            aria-current={here ? 'step' : undefined}
            className={`${chip(here)} disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:bg-transparent disabled:hover:text-white/60`}
            disabled={locked}
            key={no}
            onClick={() => onGo(no)}
            title={locked ? '제목을 먼저 입력해 주세요' : undefined}
            type="button"
          >
            <span
              aria-hidden="true"
              className={`size-1.5 rounded-full ${
                done ? 'bg-emerald-400' : here ? 'bg-slate-300' : 'bg-white/25'
              }`}
            />
            문항 {no}
          </button>
        );
      })}

      {/* 문항 칸과 같은 알약이다. 늘어서는 자리 바로 뒤에 두면 어디를 눌러야 할지 묻지 않는다 */}
      {onAdd && (
        <button className={chip(false)} onClick={onAdd} type="button">
          + 문항 추가
        </button>
      )}

      {/*
        상한에 닿으면 추가 알약이 사라진다. 사라진 이유를 말해 주지 않으면 없어진 것인지
        고장 난 것인지 알 수 없다 — 자리를 물려받아 그 까닭을 적는다.
      */}
      {atMax && (
        <span className="px-2 text-[12px] font-semibold text-white/45">
          문항은 {MAX_ITEMS}개까지 쓸 수 있어요
        </span>
      )}
    </nav>
  );
}

/**
 * 본문 좌우 여백에서 앞뒤 문항으로 넘기는 단추.
 *
 * <p>예전에는 여백 전체가 단추였다. 화면 높이의 2/3 × 여백 전체가 한 덩어리라, 그 안
 * 어디에 마우스를 올려도 반투명 사각형이 통째로 켜졌다 — 한쪽 모서리만 둥글어서 잘린
 * 판처럼 보였고, 빈 여백을 눌렀을 뿐인데 문항이 넘어가기도 했다.
 *
 * <p>그래서 정렬만 여백에 맡기고(pointer-events-none) 손이 닿는 곳은 가운데 원 하나로
 * 좁힌다. 화살표도 글자(←)가 아니라 선으로 그린다 — 글꼴이 그리는 화살표는 획이 얇고
 * 크기를 키울수록 들쭉날쭉해진다.
 *
 * <p>어디로 가는지는 원 아래 이름표로 말한다. 다음 문항인지 새 문항을 더하는 것인지
 * 모양만 봐서는 알 수 없었다.
 */
function StepArrow({
  side,
  label,
  disabled = false,
  onClick,
}: {
  side: 'left' | 'right';
  /** 눌렀을 때 닿는 곳. 호버·포커스 때만 보인다 */
  label: string;
  /** 아직 갈 수 없다. 감추지 않고 눌러지지 않는 채로 둔다 — 길이 있다는 것은 보여야 한다 */
  disabled?: boolean;
  onClick: () => void;
}) {
  const left = side === 'left';
  return (
    <div
      className={`pointer-events-none fixed top-1/2 z-10 hidden w-[calc((100vw-56rem)/2)] -translate-y-1/2 justify-center lg:flex ${
        left ? 'left-0' : 'right-0'
      }`}
    >
      <button
        /*
         * 방향까지 넣어 부른다. 이름이 "문항 1" 뿐이면 단계 줄의 같은 이름 칩과 구별되지
         * 않는다 — 읽는 도구에도, 그 이름으로 찾는 테스트에도 둘이 똑같이 보인다.
         */
        aria-label={disabled ? label : `${left ? '이전' : '다음'} — ${label}`}
        className="group pointer-events-auto relative flex items-center justify-center rounded-full p-2 focus-visible:outline-none disabled:cursor-not-allowed"
        disabled={disabled}
        onClick={onClick}
        type="button"
      >
        <span
          className={`flex size-12 items-center justify-center rounded-full backdrop-blur transition duration-200 ${
            disabled
              ? 'bg-white/5 text-white/25 ring-1 ring-white/10'
              : `bg-white/10 text-white/70 ring-1 ring-white/20 group-hover:bg-white/20 group-hover:text-white group-hover:ring-white/35 group-focus-visible:ring-2 group-focus-visible:ring-white/70 group-active:scale-95 ${
                  left ? 'group-hover:-translate-x-0.5' : 'group-hover:translate-x-0.5'
                }`
          }`}
        >
          <svg
            aria-hidden="true"
            className="size-5"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            viewBox="0 0 24 24"
          >
            <path
              d={left ? 'm14.5 5-7 7 7 7' : 'm9.5 5 7 7-7 7'}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
        {/*
          이름표는 띄워 둔다. 글 흐름에 두면 "희망 기업·직무" 와 "문항 2" 의 길이가 달라
          단추 폭이 그때그때 바뀌고, 그만큼 원이 좌우로 흔들린다.
        */}
        <span className="pointer-events-none absolute top-full left-1/2 mt-1.5 -translate-x-1/2 text-[12px] font-semibold whitespace-nowrap text-white/0 transition duration-200 group-hover:text-white/75 group-focus-visible:text-white/75">
          {label}
        </span>
      </button>
    </div>
  );
}

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
  initialPosting,
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
  const [posting, setPosting] = useState<PendingJobPosting | null>(initialPosting ?? null);
  // 등록해 둔 공고와, 그때의 회사·직무. 그 뒤에 회사나 직무를 바꾸면 다시 등록해야 한다.
  const [registered, setRegistered] = useState<{ id: string; of: string } | null>(() =>
    initial.jobContextId
      ? { id: initial.jobContextId, of: postingKey(initial.targetCompany, initial.targetPosition) }
      : null,
  );
  const [registering, setRegistering] = useState(false);
  const [postingError, setPostingError] = useState<string | null>(null);
  // 저장·검토가 멈춘 까닭. 어느 칸이 문제인지까지 담는다.
  const [saveError, setSaveError] = useState<string | null>(null);
  /*
   * 한 화면에 다 쌓아 두니 줄줄이 스크롤해야 했다. 어디에 내는지 먼저 정하고 문항을 쓰는
   * 순서가 실제로 쓰는 순서다. 이미 저장한 자소서를 다시 열 때는 고칠 것이 대개 답변이라
   * 문항부터 편다. 제목 없이 저장된 자소서는 문항부터 열 수 없으니 앞 단계로 연다.
   */
  const [step, setStep] = useState<Step>(alreadySaved && initial.title.trim() !== '' ? 1 : META_STEP);

  const touch = () => {
    setDirty(true);
    setJustSavedNotice(false);
    setPostingError(null);
    // 고치기 시작했으면 방금 짚어 준 문제는 더 이상 그 자리의 이야기가 아니다
    setSaveError(null);
  };

  const editItem = (key: string, next: Partial<WorkItem>) => {
    setItems((prev) => prev.map((item) => (item.key === key ? { ...item, ...next } : item)));
    touch();
  };

  // 문항을 더하면 그 문항으로 바로 넘어간다. 더해 놓고 찾아가게 하면 한 걸음이 더 든다.
  const addItem = () => {
    if (items.length >= MAX_ITEMS) return; // 상한을 넘겨 더하지 않는다(버튼도 그때 감춘다).
    setItems((prev) => [...prev, { key: uid(), question: '', answer: '', charLimit: 500 }]);
    setStep(items.length + 1);
    touch();
  };

  const removeItem = (key: string) => {
    if (items.length <= 1) return;
    const gone = items.findIndex((item) => item.key === key);
    setItems((prev) => prev.filter((item) => item.key !== key));
    // 지운 자리에 머물면 빈 화면이 된다. 마지막을 지웠으면 한 칸 앞으로 당긴다.
    if (gone >= 0 && step > items.length - 1) setStep(Math.max(1, items.length - 1));
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
    title: title.trim() || UNTITLED_COVER_LETTER,
    targetCompany: company.trim() || null,
    targetPosition: position.trim() || null,
    jobContextId: registered?.of === postingKey(company, position) ? registered.id : null,
    items: items.map((item) => ({
      question: item.question,
      answer: item.answer,
      // 비어 있는 제한은 0 으로 넘긴다 — 검증이 범위 밖으로 잡아 저장 전에 멈춘다
      charLimit: item.charLimit ?? 0,
    })),
  });

  /** 아직 등록하지 않은 공고. 같은 회사·직무로 이미 등록해 뒀으면 등록할 것이 없다. */
  const postingToRegister = (base: CoverLetterInput): PendingJobPosting | null => {
    const key = postingKey(base.targetCompany, base.targetPosition);
    return !posting || registered?.of === key ? null : posting;
  };

  /** 저장과 검토 모두 공고 분석이 끝난 식별자를 사용한다. 실패하면 이동하지 않고 재시도할 수 있다. */
  const inputWithPosting = async (): Promise<CoverLetterInput | null> => {
    const base = buildInput();
    // 게스트는 먼저 로그인 화면으로 보낸다. 등록 API 는 로그인 후에만 호출할 수 있다.
    if (!isLoggedIn) return base;
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
    } catch (error) {
      setPostingError(error instanceof ApiError ? error.message : '채용공고 분석에 실패했습니다. 다시 시도해 주세요.');
      return null;
    } finally {
      setRegistering(false);
    }
  };

  /*
   * 저장과 검토는 같은 자소서를 같은 조건으로 보낸다. 잘못된 곳이 있으면 보내지 않고
   * 그 칸으로 데려가서 무엇이 문제인지 말한다 — 예전에는 그대로 보내고 400 을 받았는데,
   * 받은 자리에 catch 가 없어 화면에는 아무 말도 뜨지 않았다.
   */
  const checked = (): CoverLetterInput | null => {
    const input = buildInput();
    const problem = findProblem(input);
    if (!problem) return input;
    setStep(problem.step);
    setSaveError(problem.message);
    return null;
  };

  const save = async () => {
    setSaveError(null);
    // 로그인 전에는 저장이 아니라 초안을 들고 로그인하러 가는 길이다. 쓰다 만 것도 그대로 들고 간다
    if (isLoggedIn && !checked()) return;
    setSaving(true);
    try {
      const input = await inputWithPosting();
      if (!input) return;
      await onSave(input, isLoggedIn ? null : posting);
      setDirty(false);
      setSavedOnce(true);
      setJustSavedNotice(true);
    } catch (error) {
      setSaveError(userMessage(error, '저장하지 못했어요. 잠시 후 다시 시도해 주세요.'));
    } finally {
      setSaving(false);
    }
  };

  const review = async () => {
    setSaveError(null);
    if (isLoggedIn && !checked()) return;
    setReviewing(true);
    try {
      const input = await inputWithPosting();
      if (input) {
        await onReview(input, isLoggedIn ? null : posting);
      }
    } catch (error) {
      setSaveError(userMessage(error, '검토를 시작하지 못했어요. 잠시 후 다시 시도해 주세요.'));
    } finally {
      setReviewing(false);
    }
  };

  // 질문과 답변이 다 빈 자소서를 검토에 넘기면 에이전트가 볼 것이 없다.
  const hasWriting = items.some((item) => item.question.trim() !== '' && item.answer.trim() !== '');

  /*
   * 제목이 있어야 문항으로 넘어간다. 회사·직무는 비워도 검토가 되지만 제목은 이 자소서의
   * 이름이라, 없으면 목록에서 "제목 없는 자소서" 들이 구분되지 않는다.
   */
  const metaReady = title.trim() !== '';
  const goStep = (next: Step) => setStep(next === META_STEP || metaReady ? next : META_STEP);

  return (
    /*
     * 기업 검색·모의 면접 준비와 같은 짜임이다 — 영상 위 어두운 한 장에 흰 카드를 얹는다.
     * 이 화면만 회색 바탕이라 혼자 따로 놀았다.
     *
     * overflow-hidden 은 걷었다. 기업명 검색 결과는 칸 아래로 펼쳐지는데, 결과가 많으면
     * 이 장의 밑변을 넘어서 잘려 나갔다 — 둥근 아래 모서리도, 그 아래 "그대로 쓰기" 단추도
     * 함께 사라졌다. 배경 영상은 fixed 라 이 속성과 무관하니 잘라낼 것이 없다.
     */
    <section className="relative isolate bg-slate-950 text-white">
      {/*
        화면(fixed)에 붙인다. 이 장은 문항을 늘릴수록 세로로 길어지는데, 그 길이에
        맞춰 늘이면 가로로 긴 영상이 두 배로 확대되고 좌우가 잘려 책상 귀퉁이만 남는다.
        한 화면에 고정하면 원본 비율 그대로 나오고, 스크롤해도 배경이 가만히 있어 조용하다.
      */}
      <div aria-hidden="true" className="fixed inset-0">
        {/*
          한 번만 돌고 마지막 프레임에서 멈춘다(loop 없음). 글을 쓰는 화면이라 배경이 계속
          움직이면 눈이 끌려간다. 들어올 때 한 번 살아 있다가 사진처럼 가라앉는다.
        */}
        <video
          autoPlay
          className="size-full object-cover"
          muted
          playsInline
          poster={HERO_POSTER}
          preload="metadata"
          src={HERO_VIDEO}
        />
        {/* 흰 카드가 대부분을 덮으므로 첫 화면보다 옅게 눌러야 영상이 보인다 */}
        <div className="absolute inset-0 bg-gradient-to-b from-slate-950/70 via-slate-950/62 to-slate-950/88" />
      </div>

      {/* 헤더(56)가 화면에 고정돼 있으므로 그 아래에서 시작한다 */}
      <div className="relative mx-auto w-full max-w-4xl px-6 pt-24 pb-16">
        {/* 나가는 길은 맨 위 왼쪽에 둔다. 제목과 같은 줄에 두면 제목과 무게를 다툰다 */}
        {onBack && (
          <button
            className="mb-3 block text-sm font-semibold text-white/60 transition hover:text-white"
            onClick={onBack}
            type="button"
          >
            ← 목록으로
          </button>
        )}
        <h1 className="text-2xl font-extrabold tracking-tight text-white">
          {step === META_STEP ? '회사부터 함께 정해볼까요?' : '이제 문항을 채워볼까요?'}
        </h1>
        {/*
          첫 단계에서는 설명을 걷었다 — 칸마다 라벨이 붙어 있어 한 번 더 말할 것이 없다.
          문항 단계는 그 안내가 화면에 따로 없어 남긴다.
        */}
        {step !== META_STEP && (
          <p className="mt-1 text-sm break-keep text-white/70">
            {isLoggedIn
              ? '문항을 추가·삭제하고 답변을 고친 뒤 저장하세요. 코치 다섯이 자료를 나눠 분석합니다.'
              : '로그인 없이 써 볼 수 있어요. 저장하려면 로그인하세요.'}
          </p>
        )}

        <StepRail
          atMax={step !== META_STEP && items.length >= MAX_ITEMS}
          filled={items.map((item) => item.question.trim() !== '' && item.answer.trim() !== '')}
          locked={!metaReady}
          onAdd={step === META_STEP || items.length >= MAX_ITEMS ? undefined : addItem}
          onGo={goStep}
          step={step}
        />

        {/* 제목은 이 자소서의 이름이다. 카드 안에 묻지 않고 어두운 바탕에 그대로 둔다 */}
        <div className={step === META_STEP ? 'mt-6' : 'hidden'}>
          {/*
            제목이 있어야 문항으로 넘어간다는 안내. 마무리 바에 두면 정작 채울 칸에서
            멀었다. 자리는 늘 잡아 둔다 — 접으면 첫 글자에 화면이 튄다.

            제목을 쓰면 비우지 않고 통과했다고 알린다. 빈 줄만 남으면 문구가 왜 사라졌는지
            모른 채 빈자리만 보인다. 끝말("문항을 쓸 수 있어요")을 그대로 물려 같은 말이
            조건만 풀린 것으로 읽히게 했고, 색은 단계 줄의 채워진 점과 같은 초록을 쓴다.
          */}
          <p
            aria-live="polite"
            className={`mb-1.5 h-5 text-[13px] leading-5 font-semibold ${
              metaReady ? 'text-emerald-400' : 'text-white/60'
            }`}
          >
            {metaReady ? '✓ 이제 문항을 쓸 수 있어요.' : '제목을 입력하면 문항을 쓸 수 있어요.'}
          </p>
          <input
            id="cl-title"
            aria-label="제목"
            maxLength={MAX_TITLE}
            value={title}
            onChange={(event) => {
              setTitle(event.target.value);
              touch();
            }}
            placeholder="예: 2026 상반기 백엔드 신입 지원"
            /*
             * 예시 글씨 크기를 칸 글씨(20px)와 같게 둔다. 작게 하면 같은 기준선에 앉은 채
             * 글자만 작아져 아래로 처져 보인다 — 칸 안에서 가운데가 아니게 된다. 옅은 색과
             * 보통 굵기만으로도 예시인 줄 알아본다.
             */
            className="w-full rounded-xl bg-white/10 px-4 py-3 text-xl font-bold tracking-tight text-white ring-1 ring-white/20 backdrop-blur outline-none transition placeholder:font-normal placeholder:text-white/35 focus:bg-white/15 focus:ring-2 focus:ring-white/50"
          />
        </div>

        {/*
          어디에 내는 자소서인지. 공고 주소를 넣으면 회사·직무가 저절로 채워진다.
          단계를 옮겨도 입력한 것이 날아가지 않도록 지우지 않고 감추기만 한다.
        */}
        <div
          className={`mt-4 rounded-2xl border border-slate-200 bg-white p-5 text-slate-800 shadow-sm ${
            step === META_STEP ? '' : 'hidden'
          }`}
        >
          <p className="text-xs text-slate-500">채우면 그 회사·직무 기준으로 읽어요.</p>

          <div className="mt-4">
            <JobPostingBar onParsed={applyPosting} />
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1.5 block text-sm font-semibold text-slate-700">
                지원 회사 <span className="font-medium text-slate-400">(선택)</span>
              </label>
              <CompanyPicker
                value={company}
                onChange={(next) => {
                  setCompany(next);
                  touch();
                }}
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-semibold text-slate-700" htmlFor="cl-position">
                지원 직무 <span className="font-medium text-slate-400">(선택)</span>
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
                maxLength={MAX_POSITION}
                value={position}
                onChange={(event) => {
                  setPosition(event.target.value);
                  touch();
                }}
                placeholder="지원 직무를 입력하세요"
                className="h-[42px] w-full rounded-lg border border-slate-200 px-3 text-[15px] text-slate-800 placeholder:text-[13.5px] placeholder:text-slate-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
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
        </div>

        {/* 문항을 쓰는 동안에도 어디에 내는 자소서인지 한 줄로 보인다. 누르면 앞 단계로 */}
        {step !== META_STEP && (
          <button
            className="mt-4 flex w-full flex-wrap items-center gap-x-2 gap-y-1 rounded-xl bg-white/10 px-4 py-3 text-left text-[13px] text-white/70 ring-1 ring-white/15 backdrop-blur transition hover:bg-white/15 hover:text-white"
            onClick={() => setStep(META_STEP)}
            type="button"
          >
            {/* 제목은 사용자가 쓴 글이다. 띄어쓰기 없이 길게 쓰면 이 줄을 넘어간다 */}
            <span className="min-w-0 font-bold break-keep wrap-anywhere text-white">
              {title.trim() || UNTITLED_COVER_LETTER}
            </span>
            {(company.trim() || position.trim()) && (
              <span className="min-w-0 break-keep wrap-anywhere">
                · {[company.trim(), position.trim()].filter(Boolean).join(' · ')}
              </span>
            )}
            <span className="ml-auto shrink-0 text-[12px] font-semibold text-white/50">고치기</span>
          </button>
        )}

        {/*
          단계 칩은 그대로 두고, 좌우 여백에 앞뒤로 넘길 화살표를 더한다. 답변이 길어져
          스크롤해도 자리를 지키도록 화면에 고정한다. 여백이 없는 좁은 화면에서는 감춘다 —
          칩으로 오갈 수 있다. 문항 단계에서만 낸다(첫 단계엔 이미 '문항 쓰기'가 있다).
          오른쪽은 다음 문항으로 넘어가고, 마지막 문항에서는 새 문항을 더해 그리로 옮긴다 —
          '+ 문항 추가' 를 찾지 않아도 손이 머문 자리에서 이어서 쓴다.
        */}
        {/* 앞에 아무것도 없는 첫 단계에만 왼쪽이 없다 */}
        {step !== META_STEP && (
          <StepArrow
            label={step === 1 ? '희망 기업·직무' : `문항 ${step - 1}`}
            onClick={() => goStep(step - 1)}
            side="left"
          />
        )}

        {/*
          마지막 문항에서 상한에 닿으면 이 화살표는 할 일이 없다. 그래도 남겨 두었더니
          눌러도 아무 일이 없는 단추가 되어, 더 넣을 수 없다는 사실이 "고장" 으로 읽혔다.
        */}
        {(step === META_STEP || step < items.length || items.length < MAX_ITEMS) && (
          <StepArrow
            // 제목이 없으면 문항으로 넘어갈 수 없다. 눌러도 안 되는 대신 왜 안 되는지 적는다
            disabled={step === META_STEP && !metaReady}
            label={
              step === META_STEP
                ? metaReady
                  ? '문항 1'
                  : '제목을 먼저 입력해 주세요'
                : step < items.length
                  ? `문항 ${step + 1}`
                  : '문항 추가'
            }
            onClick={() => (step < items.length ? goStep(step + 1) : addItem())}
            side="right"
          />
        )}

        {/* 한 화면에 한 문항만. 나머지는 지우지 않고 감춘다 — 입력한 것이 날아가면 안 된다 */}
        <div className={step === META_STEP ? 'hidden' : 'mt-4'}>
          {items.map((item, index) => (
            <section
              key={item.key}
              className={`rounded-2xl border border-slate-200 bg-white p-5 text-slate-800 shadow-sm ${
                step === index + 1 ? '' : 'hidden'
              }`}
            >
              {/*
                회색 머리띠를 걷었다. 번호 알약과 삭제만 남기면 정작 읽어야 할 질문·답변이
                먼저 눈에 들어온다.
              */}
              <div className="mb-3 flex flex-wrap items-center gap-2">
                {/* 번호는 몇 번째인지 알려 줄 뿐이다. 카드 바탕에 가까운 회색으로 눌러 둔다 */}
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-[12px] font-bold text-slate-600">
                  {index + 1}
                </span>
                <span className="text-sm font-bold text-slate-700">문항 {index + 1}</span>

                {items.length > 1 && (
                  <button
                    onClick={() => removeItem(item.key)}
                    className="ml-auto rounded-lg px-3 py-1.5 text-[13px] font-semibold text-slate-400 transition hover:bg-rose-50 hover:text-rose-600"
                    type="button"
                  >
                    삭제
                  </button>
                )}
              </div>

              <div className="space-y-3">
              <div className="flex flex-col gap-3 sm:flex-row">
                <div className="flex-1">
                  <label className="mb-1 block text-[12px] font-medium text-slate-500" htmlFor={`question-${item.key}`}>질문</label>
                  <input
                    id={`question-${item.key}`}
                    value={item.question}
                    onChange={(event) => editItem(item.key, { question: event.target.value })}
                    maxLength={MAX_QUESTION}
                    placeholder="예: 지원 동기와 입사 후 포부를 기술하시오"
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-[15px] text-slate-800 placeholder:text-[13.5px] placeholder:text-slate-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
                  />
                </div>
                <div className="sm:w-32">
                  <label className="mb-1 block text-[12px] font-medium text-slate-500" htmlFor={`limit-${item.key}`}>글자 수 제한</label>
                  <input
                    /*
                     * type="number" 가 아니다. React 는 숫자 입력칸의 DOM 값을 느슨 비교로만
                     * 맞춰서, "00…050" 과 50 을 같다고 보고 친 글자를 그대로 남겨 두었다.
                     * 글자로 받고 숫자만 남기면 칸에 보이는 것과 실제 제한이 늘 같다.
                     */
                    id={`limit-${item.key}`}
                    type="text"
                    inputMode="numeric"
                    value={item.charLimit ?? ''}
                    onChange={(event) =>
                      editItem(item.key, { charLimit: normalizeCharLimit(event.target.value) })
                    }
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-[15px] text-slate-800 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
                  />
                </div>
              </div>
              <div>
                <label className="mb-1 block text-[12px] font-medium text-slate-500" htmlFor={`answer-${item.key}`}>답변</label>
                <textarea
                  id={`answer-${item.key}`}
                  value={item.answer}
                  onChange={(event) => editItem(item.key, { answer: event.target.value })}
                  rows={8}
                  maxLength={item.charLimit ?? MAX_ANSWER}
                  placeholder="답변을 붙여넣거나 입력하세요"
                  className="w-full resize-y rounded-lg border border-slate-200 p-3 text-[15px] leading-7 text-slate-700 placeholder:text-[13.5px] placeholder:text-slate-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
                />
                <div className="mt-1.5 text-right text-[12px] text-slate-400">
                  <span
                    className={
                      item.charLimit !== null && item.answer.length > item.charLimit
                        ? 'font-bold text-rose-500'
                        : ''
                    }
                  >
                    {item.answer.length}
                  </span>{' '}
                  / {item.charLimit ?? '—'}자
                </div>
              </div>
            </div>
          </section>
        ))}
      </div>

        {/*
          공고 분석이 실패하면 이동하지 않고 여기서 알린다. 어느 단계에서 눌렀든 보여야
          하므로 단계별로 감추는 칸 바깥, 누른 단추 바로 옆에 둔다.
        */}
        {postingError && (
          <p
            className="mt-4 rounded-xl bg-rose-500/15 px-4 py-3 text-sm font-semibold text-rose-200 ring-1 ring-rose-400/30"
            role="alert"
          >
            {postingError}
          </p>
        )}

        {/*
          저장이 멈춘 까닭. 단계별로 감추는 칸 바깥에 둔다 — 문제가 있는 문항으로 옮겨
          가면서 함께 보여야 하는데, 칸 안에 두면 그 칸이 감춰질 때 같이 사라진다.
        */}
        {saveError && (
          <p
            className="mt-4 rounded-xl bg-rose-500/15 px-4 py-3 text-sm font-semibold break-keep text-rose-200 ring-1 ring-rose-400/30"
            role="alert"
          >
            {saveError}
          </p>
        )}

        {/* 상자를 걷었다. 왼쪽이 지금 상태, 오른쪽이 다음 걸음인 짜임은 그대로다 */}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 text-white">
          {/* 첫 단계에서 할 말은 모두 위로 올라갔다 — 여기에는 단추만 남는다 */}
          {step !== META_STEP && (
            <div className="min-w-0">
              <p className="text-sm font-bold">
                {!hasWriting
                  ? '질문과 답변을 채우면 검토를 받을 수 있어요.'
                  : isLoggedIn
                    ? '코치 다섯이 자료를 나눠 분석합니다.'
                    : '검토를 받으려면 로그인이 필요해요.'}
              </p>
              <p className="mt-0.5 text-xs break-keep text-white/60">
                {isLoggedIn
                  ? '저장한 뒤 검토 방으로 넘어갑니다. 문항은 위에서 오갈 수 있어요.'
                  : '로그인하면 쓰던 자소서가 그대로 남습니다.'}
              </p>
            </div>
          )}
          <div className="ml-auto flex shrink-0 items-center gap-2">
            <SaveArea
              isLoggedIn={isLoggedIn}
              dirty={dirty}
              savedOnce={savedOnce}
              saving={saving}
              registering={registering}
              justSaved={justSavedNotice}
              onSave={save}
            />
            {/* 첫 단계의 다음 걸음은 검토가 아니라 문항 쓰기다 */}
            {step === META_STEP ? (
              <button
                className="rounded-full bg-white px-7 py-3 text-sm font-bold text-slate-950 transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:translate-y-0"
                disabled={!metaReady}
                onClick={() => setStep(1)}
                type="button"
              >
                문항 쓰기 →
              </button>
            ) : (
              <button
                onClick={review}
                disabled={reviewing || registering || saving || !hasWriting}
                className="rounded-full bg-white px-7 py-3 text-sm font-bold text-slate-950 transition hover:-translate-y-0.5 disabled:opacity-40 disabled:hover:translate-y-0"
                type="button"
              >
                {registering || reviewing ? <Spinner className="mr-1.5" /> : null}
                {registering ? '공고 분석 중…' : reviewing ? '여는 중…' : 'AI 검토'}
              </button>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

type PostingStatus = 'idle' | 'loading' | 'done' | 'error';

/** AI 쪽 OCR 예산(UPLOAD_OCR_MAX_IMAGES)과 맞춘다. 더 받아도 뒤쪽은 읽히지 않는다. */
const MAX_POSTING_IMAGES = 8;

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
  // 붙여넣은 공고 이미지. 공고는 위에서 아래로 읽히므로 넣은 순서를 지킨다.
  const [images, setImages] = useState<File[]>([]);

  const describeFailure = (error: unknown, fallback: string) => {
    setStatus('error');
    if (error instanceof ApiError && isRateLimited(error)) {
      setMessage('요청이 많습니다. 잠시 후 다시 시도해 주세요.');
      return;
    }
    if (error instanceof ApiError && error.status === 413) {
      setMessage('이미지 용량이 너무 큽니다. 장수를 줄이거나 화면을 나눠 캡처해 주세요.');
      return;
    }
    setMessage(error instanceof ApiError ? error.message : fallback);
  };

  const urlReady = url.trim() !== '' && url.trim() !== blockedUrl;

  /*
   * 주소와 이미지는 각자 단추를 갖는다. 예전에는 단추 하나가 둘을 겸해서, 이미지를 넣어 놓고
   * 엉뚱하게 주소 칸 옆 단추를 눌러야 했다 — 무엇을 읽는 단추인지 화면만 봐서는 알 수 없었다.
   */
  const confirmUrl = async () => {
    const target = url.trim();
    if (!urlReady) return;
    setStatus('loading');
    setMessage('');
    try {
      const result = await parseJobPosting(target);
      onParsed(result.companyName, result.positions, result.sourceUrl ?? target, result.sourceKey);
      // 잘 됐다는 말은 하지 않는다. 회사·직무 칸이 채워진 것으로 이미 보인다.
      setStatus('done');
      setMessage('');
    } catch (error) {
      if (error instanceof ApiError && error.code === 'JOB_POSTING_PARSE_FAILED') {
        // 같은 URL 재시도는 무의미 → 그 주소를 잠그고 이미지/직접 입력으로 유도한다.
        setBlockedUrl(target);
        setStatus('error');
        setMessage('이 공고는 주소로 읽히지 않아요. 공고 이미지를 붙여넣거나 직접 입력해 주세요.');
        return;
      }
      describeFailure(error, '공고를 확인하지 못했습니다. 주소를 다시 확인해 주세요.');
    }
  };

  /** 붙여넣은 이미지는 원본 그대로 담는다. 줄이고 자르는 일은 보낼 때 한다. */
  const addImages = (candidates: File[]) => {
    const picked = candidates.filter((file) => file.type.startsWith('image/'));
    if (picked.length === 0) return;
    setImages((prev) => [...prev, ...picked].slice(0, MAX_POSTING_IMAGES));
    if (status === 'error') {
      setStatus('idle');
      setMessage('');
    }
  };

  const confirmImages = async () => {
    if (images.length === 0) return;
    setStatus('loading');
    setMessage('이미지를 준비하는 중…');
    try {
      // 전체 페이지 캡처는 세로가 아주 길다. 통째로 보내면 프록시가 413 으로 끊으므로
      // 여기서 띠 모양으로 잘라 조각마다 JPEG 로 줄인다.
      const prepared = await preparePostingImages(images, (done) =>
        setMessage(`이미지를 준비하는 중… ${done}조각`),
      );
      const total = prepared.reduce((sum, file) => sum + file.size, 0);
      if (
        total > MAX_POSTING_IMAGES_BYTES ||
        prepared.some((file) => file.size > MAX_POSTING_IMAGE_BYTES)
      ) {
        setStatus('error');
        setMessage('이미지 용량이 너무 큽니다. 공고를 나눠 캡처해 주세요.');
        return;
      }
      // 여기서부터가 대기의 대부분이다(조각당 OCR 6초, 동시 4개). 몇 초쯤 걸리는지
      // 알려 주지 않으면 멈춘 것처럼 보인다.
      setMessage(`공고를 읽는 중… 조각 ${prepared.length}개`);
      const result = await parseJobPostingImages(prepared);
      onParsed(result.companyName, result.positions, result.sourceUrl ?? '', result.sourceKey);
      setStatus('done');
      setMessage('');
      setImages([]);
    } catch (error) {
      describeFailure(error, '이미지에서 공고를 읽지 못했습니다.');
    }
  };

  return (
    <div>
      <label className="mb-1.5 block text-sm font-semibold text-slate-700" htmlFor="cl-posting-url">
        채용공고 URL <span className="font-medium text-slate-400">(선택)</span>
      </label>
      <div className="flex flex-col gap-2 sm:flex-row">
        {/* 무엇을 넣는 칸인지 글을 읽기 전에 알아보게 한다. 기업명 검색 칸과 같은 자리·크기다 */}
        <div className="relative min-w-0 flex-1">
          <svg
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 left-[13px] size-4 -translate-y-1/2 text-slate-400"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            viewBox="0 0 24 24"
          >
            <path d="M10 13a5 5 0 0 0 7.07 0l2-2a5 5 0 0 0-7.07-7.07l-1.5 1.5" strokeLinecap="round" />
            <path d="M14 11a5 5 0 0 0-7.07 0l-2 2a5 5 0 0 0 7.07 7.07l1.5-1.5" strokeLinecap="round" />
          </svg>
          <input
            id="cl-posting-url"
            // 백엔드 JobPostingParseRequest 의 @Size(max=2000) 과 같은 값
            maxLength={2000}
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
                confirmUrl();
              }
            }}
            type="url"
            inputMode="url"
            placeholder="주소를 넣고 확인하면 회사·직무를 대신 채워 드려요"
            className="h-[42px] w-full rounded-lg border border-slate-200 pr-3 pl-9 text-[15px] text-slate-800 placeholder:text-[13.5px] placeholder:text-slate-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
          />
        </div>
        <button
          onClick={confirmUrl}
          disabled={status === 'loading' || !urlReady}
          className="h-[42px] w-full shrink-0 rounded-lg bg-blue-600 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300 sm:w-[92px]"
          type="button"
        >
          {status === 'loading' ? <Spinner className="mr-1.5" /> : null}
          {status === 'loading' ? '확인 중…' : '확인'}
        </button>
      </div>

      {/*
        본문이 이미지인데 그 주소가 서버가 받는 HTML 에 없어 주소로는 못 읽는 공고가 있다.
        화면에는 보이므로 복사해 온 이미지를 그대로 받는다.
      */}
      <div className="mt-2 flex flex-col gap-2 sm:flex-row">
        {/*
          옆 단추(42px)에 맞춰 늘어나는 칸이라, 안의 것을 세로 가운데에 두지 않으면 위에 붙어
          윗줄 입력칸과 눈높이가 어긋난다. 이미지를 넣으면 알약이 줄로 늘어나므로 높이는
          고정하지 않고 최소값만 준다.
        */}
        <div
          className="flex min-h-[42px] min-w-0 flex-1 items-center rounded-lg border border-dashed border-slate-300 px-3 py-2 focus-within:border-blue-400"
          onPaste={(event) => {
            const pasted = Array.from(event.clipboardData.files);
            if (!pasted.some((file) => file.type.startsWith('image/'))) return;
            event.preventDefault();
            addImages(pasted);
          }}
          tabIndex={0}
        >
          {images.length === 0 ? (
            <span className="flex items-center gap-2 text-[13.5px] text-slate-400">
              <svg
                aria-hidden="true"
                className="size-4 shrink-0"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                viewBox="0 0 24 24"
              >
                <rect height="18" rx="2" width="18" x="3" y="3" />
                <circle cx="8.5" cy="8.5" r="1.5" />
                <path d="m21 15-4.5-4.5L5.5 21" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span className="min-w-0">
                여기를 누르고 공고 이미지를 <kbd className="rounded bg-slate-100 px-1">Ctrl</kbd>+
                <kbd className="rounded bg-slate-100 px-1">V</kbd> 로 붙여넣으세요
              </span>
            </span>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              {images.map((image, index) => (
                <span
                  key={`${image.name}-${index}`}
                  className="inline-flex items-center gap-1 rounded bg-slate-100 px-2 py-1 text-[12px] text-slate-600"
                >
                  {index + 1}. {image.name || '붙여넣은 이미지'}
                  <button
                    aria-label={`${index + 1}번 이미지 빼기`}
                    className="text-slate-400 hover:text-slate-700"
                    onClick={() => setImages((prev) => prev.filter((_, at) => at !== index))}
                    type="button"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        <label className="flex h-[42px] w-full shrink-0 cursor-pointer items-center justify-center rounded-lg border border-slate-200 text-sm font-semibold text-slate-600 transition hover:bg-slate-50 sm:w-[92px]">
          파일 선택
          <input
            aria-label="공고 이미지 선택"
            type="file"
            accept="image/png,image/jpeg,image/webp"
            multiple
            onChange={(event) => {
              addImages(Array.from(event.target.files ?? []));
              event.target.value = '';
            }}
            className="sr-only"
          />
        </label>
      </div>

      {/*
        몇 장까지 되는지는 넣기 전에 알아야 한다. 용량은 숫자로 못 박지 않는다 — 보낼 때
        띠로 잘라 다시 줄이므로, 원본 크기로는 되는지 안 되는지 말할 수 없다.
      */}
      <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2">
        <p className="text-[12px] text-slate-400">
          최대 {MAX_POSTING_IMAGES}장 · 긴 캡처는 알아서 잘라 보내요
        </p>
        {images.length > 0 && (
          <button
            className="h-[34px] shrink-0 rounded-lg bg-blue-600 px-4 text-[13px] font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={status === 'loading'}
            onClick={confirmImages}
            type="button"
          >
            {status === 'loading' ? <Spinner className="mr-1.5" /> : null}
            {status === 'loading' ? '읽는 중…' : `이미지 ${images.length}장으로 확인`}
          </button>
        )}
      </div>

      <p
        className={[
          message ? 'mt-2 text-[12.5px]' : 'sr-only',
          status === 'error' ? 'text-amber-700' : 'text-slate-400',
        ].join(' ')}
        role={status === 'error' ? 'alert' : 'status'}
      >
        {message}
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
        className="rounded-full px-6 py-3 text-sm font-bold text-white/80 ring-1 ring-white/30 transition hover:bg-white/10 hover:text-white disabled:opacity-40"
        type="button"
      >
        {saving ? <Spinner className="mr-1.5" /> : null}
        {saving ? '이동 중…' : '로그인하고 저장'}
      </button>
    );
  }

  return (
    <div className="flex items-center gap-2">
      {justSaved ? (
        <span role="status" className="text-[13px] font-semibold text-emerald-300">
          저장했습니다 ✓
        </span>
      ) : (
        savedOnce && !dirty && <span className="text-[12.5px] font-medium text-emerald-300">저장됨 ✓</span>
      )}
      <button
        onClick={onSave}
        disabled={saving || registering || (savedOnce && !dirty)}
        className="rounded-full px-6 py-3 text-sm font-bold text-white/80 ring-1 ring-white/30 transition hover:bg-white/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
        type="button"
      >
        {saving ? <Spinner className="mr-1.5" /> : null}
        {saving ? '저장 중…' : '저장'}
      </button>
    </div>
  );
}

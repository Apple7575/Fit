import { useEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { ApiError, isRateLimited } from '../../api/client';
import { userMessage } from '../../api/errorMessage';
import { Spinner } from '../../components/common/Spinner';
import { CompanyPicker } from './CompanyPicker';
import { ImageIcon, LinkIcon, LoadingDots, PencilIcon, SendIcon, TrashIcon, UploadIcon } from './icons';
import { resolveCompany } from './resolveCompany';
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

/**
 * 작성 화면의 입력칸이 함께 쓰는 모양. 질문·글자 수·답변·제목 창이 한 가족으로 보이게
 * 테두리·곡률·글자색을 맞춘다. 눌러도 모양이 바뀌지 않는다 — 파란 테두리·번짐은
 * 걷어 달라고 했다(기업 분석 검색칸·공고 주소 칸과 같은 규칙).
 */
const FIELD =
  'rounded-2xl border border-slate-300 bg-white text-[15px] text-slate-900 outline-none transition-colors placeholder:text-slate-400';

/** 답변 칸이 처음 차지하는 높이와 늘어날 수 있는 끝. 넘으면 칸 안에서 스크롤한다 */
const ANSWER_MIN_HEIGHT = 200;
const ANSWER_MAX_HEIGHT = 520;

/** 친 만큼 답변 칸을 늘린다. 처음부터 커다란 빈 칸이 화면을 다 차지하지 않게 한다 */
const growAnswer = (el: HTMLTextAreaElement | null) => {
  if (!el) return;
  el.style.height = 'auto';
  const next = Math.min(Math.max(el.scrollHeight, ANSWER_MIN_HEIGHT), ANSWER_MAX_HEIGHT);
  el.style.height = `${next}px`;
  el.style.overflowY = el.scrollHeight > ANSWER_MAX_HEIGHT ? 'auto' : 'hidden';
};

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
  atMax,
  onGo,
  onAdd,
}: {
  step: Step;
  /** 문항별로 질문·답변이 채워졌는지. 어디까지 썼는지 한눈에 보인다 */
  filled: boolean[];
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

  const writing = step !== META_STEP;
  /*
   * 큰 걸음은 둘이다 — 어디에 낼지 정하고, 쓴다. 예전에는 "문항 1" 칩이 두 번째 걸음을
   * 대신해서 첫 문항을 가리키는 것으로 읽혔다. 걸음은 번호와 선으로 잇고, 문항 칩은
   * 쓰는 걸음에 들어선 뒤에만 그 아래 줄에 편다.
   */
  const phase = (here: boolean, done: boolean) =>
    `flex size-7 shrink-0 items-center justify-center rounded-full text-[12px] font-bold tabular-nums transition ${
      here
        ? 'bg-blue-600 text-white shadow-[0_0_0_4px_rgba(37,99,235,0.2)]'
        : done
          ? 'bg-blue-600/20 text-blue-300 ring-1 ring-blue-400/50'
          : 'text-slate-400 ring-1 ring-slate-500'
    }`;

  return (
    <nav aria-label="작성 단계" className="mt-7">
      <ol className="flex items-center gap-3 sm:gap-4">
        <li>
          <button
            aria-current={step === META_STEP ? 'step' : undefined}
            className="group flex items-center gap-2.5 rounded-full py-1 pr-2 transition"
            onClick={() => onGo(META_STEP)}
            type="button"
          >
            <span aria-hidden="true" className={phase(!writing, writing)}>{writing ? '✓' : '01'}</span>
            <span
              className={`text-sm font-bold transition ${
                writing ? 'text-slate-300 group-hover:text-white' : 'text-white'
              }`}
            >
              기업·직무 설정
            </span>
          </button>
        </li>
        {/* 앞 걸음을 마치면 선이 파랗게 찬다 */}
        <li aria-hidden="true" className="h-px w-10 shrink-0 bg-slate-600 sm:w-24">
          <span
            className={`block h-full bg-blue-500/60 transition-[width] duration-300 ${writing ? 'w-full' : 'w-0'}`}
          />
        </li>
        <li>
          <button
            aria-current={writing ? 'step' : undefined}
            className="group flex items-center gap-2.5 rounded-full py-1 pr-2 transition"
            onClick={() => onGo(writing ? step : 1)}
            type="button"
          >
            <span aria-hidden="true" className={phase(writing, false)}>02</span>
            <span
              className={`text-sm font-bold transition ${
                writing ? 'text-white' : 'text-slate-400 group-hover:text-slate-200'
              }`}
            >
              자기소개서 작성
            </span>
          </button>
        </li>
      </ol>

      {writing && (
      <div className="mt-4 flex flex-wrap items-center gap-2">
      {filled.map((done, index) => {
        const no = index + 1;
        const here = step === no;
        return (
          <button
            aria-current={here ? 'step' : undefined}
            className={chip(here)}
            key={no}
            onClick={() => onGo(no)}
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
      {/*
        탭(문항 N)과 같은 알약이면 이것도 탭처럼 읽혔다. 점선 테두리에 옅은 글자로 두어
        "고르는 것" 이 아니라 "더하는 것" 임을 모양으로 가른다.
      */}
      {onAdd && (
        <button
          className="ml-1 flex items-center gap-1 rounded-full border border-dashed border-white/35 px-3.5 py-2 text-[13px] font-semibold text-slate-300 transition-colors hover:border-white/55 hover:bg-white/[0.06] hover:text-white"
          onClick={onAdd}
          type="button"
        >
          <span aria-hidden="true" className="text-[15px] leading-none">+</span> 문항 추가
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
      </div>
      )}
    </nav>
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
  /*
   * 링크가 없을 때 펼치는 칸. 셋(이미지·파일·직접 입력)은 한 번에 하나만 연다 — 같은 단추를
   * 다시 누르면 접고, 다른 단추를 누르면 바꿔 편다. 회사·직무를 이미 정해 두고 연
   * 자소서는 그 칸을 편 채로 연다.
   */
  const [alt, setAlt] = useState<AltInput>(() =>
    (initial.targetCompany ?? '').trim() !== '' || (initial.targetPosition ?? '').trim() !== ''
      ? 'manual'
      : null,
  );
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
    // 읽어 온 회사·직무를 바로 확인하고 고칠 수 있게 그 칸을 편다(이미지 칸은 접힌다)
    setAlt('manual');
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
      setPostingError(userMessage(error, '채용공고 분석에 실패했습니다. 다시 시도해 주세요.'));
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
    // 제목 문제는 앞 단계로 돌려보내지 않는다. 지금 자리에서 제목 창만 다시 연다
    if (problem.field === 'title') {
      setTitleError(problem.message);
      setTitleModal(step === META_STEP ? 'start' : 'edit');
      return null;
    }
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
  const showEntry = alt === 'manual';
  /*
   * 제목은 마지막에 작은 창으로 묻는다. 본문에 칸으로 두니 공고를 넣는 단계와 이름을 짓는
   * 단계가 한 화면에 섞여 길어졌다. 입력 방식(링크·이미지·파일·직접)과 상관없이 문항으로
   * 넘어가는 단추(문항 쓰러가기)는 늘 이 창을 거친다. 단계 줄·화살표는 제목이 이미 있으면
   * 곧장 넘어간다 — 오갈 때마다 창을 띄우면 성가시다.
   */
  /*
   * 제목 창은 둘로 쓴다. 'start' 는 문항으로 넘어가기 직전(확인하면 문항 1로), 'edit' 는
   * 문항을 쓰다가 제목만 고칠 때(확인해도 그 자리에 머문다). null 이면 닫혀 있다.
   */
  const [titleModal, setTitleModal] = useState<'start' | 'edit' | null>(null);
  /*
   * 공고(주소·이미지)를 읽는 중. 끝나면 회사·직무가 바뀌므로 그 전에 문항으로 넘어가면
   * 읽기 전 값으로 제목을 짓고 넘어가 버린다. 읽는 동안은 넘어가는 길을 잠근다.
   */
  const [postingBusy, setPostingBusy] = useState(false);
  const [titleError, setTitleError] = useState<string | null>(null);
  const openTitleModal = (mode: 'start' | 'edit' = 'start') => {
    setTitleError(null);
    setTitleModal(mode);
  };
  const goStep = (next: Step) => {
    if (next !== META_STEP && postingBusy) return;
    if (next === META_STEP || metaReady) setStep(next);
    else openTitleModal();
  };

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
        <div className="absolute inset-0 bg-gradient-to-b from-slate-950/78 via-slate-950/72 to-slate-950/90" />
      </div>

      {/* 헤더(56)가 화면에 고정돼 있으므로 그 아래에서 시작한다 */}
      <div className="relative mx-auto w-full max-w-[960px] px-5 pt-20 pb-16 sm:px-8">
        {/*
          나가는 길은 맨 위 왼쪽, 본문과 같은 기준선에 둔다. 단추 모양을 입히지 않은 글자라
          제목과 무게를 다투지 않는다.
        */}
        {onBack && (
          <button
            className="mb-4 inline-flex items-center gap-1.5 text-sm font-semibold text-slate-400 transition-colors hover:text-white"
            onClick={onBack}
            type="button"
          >
            <svg aria-hidden="true" className="size-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path d="M19 12H5m6-6-6 6 6 6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            돌아가기
          </button>
        )}
        <h1 className="text-[28px] leading-tight font-extrabold tracking-tight text-white sm:text-[32px]">
          {step === META_STEP ? '회사부터 함께 정해볼까요?' : '이제 문항을 채워볼까요?'}
        </h1>
        {/*
          첫 단계에도 한 줄을 둔다. 할 일은 링크를 넣는 것인데, 왜 넣는지 말하지 않으면
          "회사부터" 와 링크 칸이 이어지지 않는다.
        */}
        <p className="mt-2.5 text-[15px] break-keep text-slate-400">
          {step === META_STEP
            ? '채용 공고를 등록하면 기업과 직무 정보를 자동으로 정리해드려요.'
            : isLoggedIn
              ? '문항을 추가·삭제하고 답변을 고친 뒤 저장하세요. 코치 다섯이 자료를 나눠 분석합니다.'
              : '로그인 없이 써 볼 수 있어요. 저장하려면 로그인하세요.'}
        </p>

        <StepRail
          atMax={step !== META_STEP && items.length >= MAX_ITEMS}
          filled={items.map((item) => item.question.trim() !== '' && item.answer.trim() !== '')}
          onAdd={step === META_STEP || items.length >= MAX_ITEMS ? undefined : addItem}
          onGo={goStep}
          step={step}
        />

        {/*
          TIO 처럼 공고 링크 한 칸을 앞에 세운다. 링크가 없을 때의 길(이미지·파일·직접 입력)은
          그 아래 단추로 비켜 둔다 — 셋을 한꺼번에 펼쳐 두니 무엇부터 할지 몰랐다.
          단계를 옮겨도 입력한 것이 날아가지 않도록 지우지 않고 감추기만 한다.
        */}
        <div className={step === META_STEP ? 'mt-8' : 'hidden'}>
          <JobPostingBar alt={alt} onAlt={setAlt} onBusyChange={setPostingBusy} onParsed={applyPosting} />
        </div>

        {/*
          회사·직무는 링크를 읽었거나 직접 입력을 골랐을 때 연다. 처음부터 두면 링크 칸과
          나란히 서서 어느 쪽을 채워야 하는지 헷갈렸다.
        */}
        <div
          className={`mx-auto mt-3 w-full max-w-[780px] rounded-3xl border border-slate-200 bg-white p-5 text-slate-800 shadow-sm sm:p-6 ${
            step === META_STEP && showEntry ? '' : 'hidden'
          }`}
        >
          <div className="grid gap-4 sm:grid-cols-2">
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
                className="h-12 w-full rounded-full border border-slate-300 px-5 text-[15px] text-slate-800 transition placeholder:text-slate-400 focus:outline-none"
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

        {/*
          문항을 쓰는 동안에도 어디에 내는 자소서인지 한 줄로 보인다. 알려 주는 줄이라 옅고
          낮게 둔다. 예전에는 줄 전체가 "고치기" 단추라 누르면 기업·직무 단계로 넘어갔는데,
          무엇을 고치는지 알 수 없었다 — 이제 오른쪽 작은 단추로 제목만 이 자리에서 고친다.
          회사·직무는 단계 줄의 '기업·직무 설정' 으로 돌아가 고친다.
        */}
        {step !== META_STEP && (
          <div className="mt-4 flex items-center gap-3 rounded-2xl bg-white/[0.06] py-2 pr-2 pl-4 text-[13px] text-slate-400 ring-1 ring-white/10">
            {/* 제목은 사용자가 쓴 글이다. 길면 줄여 보이고, 단추는 줄을 바꾸지 않는다 */}
            <p className="min-w-0 flex-1 truncate">
              <span className="font-bold text-white">{title.trim() || UNTITLED_COVER_LETTER}</span>
              {(company.trim() || position.trim()) && (
                <span> · {[company.trim(), position.trim()].filter(Boolean).join(' · ')}</span>
              )}
            </p>
            <button
              className="inline-flex shrink-0 items-center gap-1.5 rounded-xl px-2.5 py-1.5 text-[12.5px] font-semibold whitespace-nowrap text-slate-400 transition-colors hover:bg-white/[0.08] hover:text-white"
              onClick={() => openTitleModal('edit')}
              type="button"
            >
              <PencilIcon className="size-4" />
              제목 수정
            </button>
          </div>
        )}

        {/*
          좌우 여백의 커다란 원형 화살표(앞뒤 문항)는 걷었다. 배경을 넘기는 단추처럼 보여
          시선만 끌었고, 문항 사이는 위 탭으로 오간다.
        */}
        {/* 한 화면에 한 문항만. 나머지는 지우지 않고 감춘다 — 입력한 것이 날아가면 안 된다 */}
        <div className={step === META_STEP ? 'hidden' : 'mt-4'}>
          {items.map((item, index) => (
            <section
              key={item.key}
              className={`rounded-3xl border border-slate-200 bg-white p-6 text-slate-800 shadow-sm ${
                step === index + 1 ? '' : 'hidden'
              }`}
            >
              {/*
                회색 머리띠를 걷었다. 번호 알약과 삭제만 남기면 정작 읽어야 할 질문·답변이
                먼저 눈에 들어온다.
              */}
              <div className="mb-5 flex flex-wrap items-center gap-2">
                {/* 번호는 몇 번째인지 알려 줄 뿐이다. 카드 바탕에 가까운 회색으로 눌러 둔다 */}
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-[12px] font-bold text-slate-600">
                  {index + 1}
                </span>
                <span className="text-sm font-bold text-slate-700">문항 {index + 1}</span>

                {/*
                  이 문항을 지우는 단추라 카드 머리 오른쪽 끝에 둔다. 지우는 일이라 누르기 전부터
                  옅은 빨강으로 알린다(진한 빨강 단추처럼 보이지는 않게). 문항은 적어도 하나
                  있어야 하므로 하나만 남으면 단추가 없다 — removeItem 도 같은 조건으로 막는다.
                */}
                {items.length > 1 && (
                  <button
                    aria-label="문항 삭제"
                    className="ml-auto flex size-9 items-center justify-center rounded-xl bg-[rgba(220,80,80,0.10)] text-[#d65c5c] transition-colors hover:bg-[rgba(220,80,80,0.16)] hover:text-[#c44848]"
                    onClick={() => removeItem(item.key)}
                    title="문항 삭제"
                    type="button"
                  >
                    <TrashIcon />
                  </button>
                )}
              </div>

              <div className="space-y-5">
              {/*
                질문이 주인공이고 글자 수 제한은 곁들이는 값이다. 두 칸이 같은 크기로 서니
                제한 칸이 질문만큼 눈에 띄었다. 제한은 숫자만 들어가는 작은 칸에 "자" 를 붙인다.
              */}
              <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
                <div className="min-w-0 flex-1">
                  <label className="mb-1.5 block text-[13px] font-semibold text-slate-600" htmlFor={`question-${item.key}`}>질문</label>
                  <input
                    id={`question-${item.key}`}
                    value={item.question}
                    onChange={(event) => editItem(item.key, { question: event.target.value })}
                    maxLength={MAX_QUESTION}
                    placeholder="예: 지원 동기와 입사 후 포부를 기술하시오"
                    className={`h-12 w-full px-4 ${FIELD}`}
                  />
                </div>
                <div className="shrink-0">
                  <label className="mb-1.5 block text-[13px] font-semibold text-slate-600" htmlFor={`limit-${item.key}`}>글자 수 제한</label>
                  <div className="flex items-center gap-2">
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
                      className={`h-12 w-24 px-3 text-right tabular-nums ${FIELD}`}
                    />
                    <span className="text-[14px] font-medium text-slate-500">자</span>
                  </div>
                </div>
              </div>
              <div>
                <label className="mb-1.5 block text-[13px] font-semibold text-slate-600" htmlFor={`answer-${item.key}`}>답변</label>
                <textarea
                  id={`answer-${item.key}`}
                  value={item.answer}
                  onChange={(event) => {
                    growAnswer(event.target);
                    editItem(item.key, { answer: event.target.value });
                  }}
                  // 그릴 때마다 다시 잰다. 감춰져 있던 문항은 잴 높이가 없어서, 보이게 된 뒤 재야 맞다
                  ref={(el) => growAnswer(el)}
                  maxLength={item.charLimit ?? MAX_ANSWER}
                  placeholder="답변을 붙여넣거나 입력하세요"
                  style={{ minHeight: ANSWER_MIN_HEIGHT }}
                  className={`block w-full resize-none px-4 py-3 leading-7 ${FIELD}`}
                />
                {/*
                  칸 바로 아래 오른쪽. 평소에는 옅게, 제한의 90% 를 넘으면 주황, 넘치면 빨강.
                */}
                <p
                  className={`mt-2 text-right text-[12.5px] tabular-nums ${
                    item.charLimit !== null && item.answer.length > item.charLimit
                      ? 'font-bold text-rose-500'
                      : item.charLimit !== null && item.answer.length >= item.charLimit * 0.9
                        ? 'font-semibold text-amber-600'
                        : 'text-slate-400'
                  }`}
                >
                  {item.answer.length} / {item.charLimit ?? '—'}자
                </p>
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
        {/*
          입력은 여기서 끝나고 아래는 다음 단계로 가는 자리다. 둘이 한 덩어리로 붙어 보여
          간격을 벌리고, 선은 본문보다 조금 짧고 옅게 그어 구역만 가른다. 단추는 오른쪽 그대로.
        */}
        <div aria-hidden="true" className="mx-auto mt-20 h-px w-[94%] bg-white/10" />
        <div className="mt-7 flex flex-col gap-4 text-white sm:flex-row sm:items-center sm:justify-between">
          {step !== META_STEP && (
            <div className="min-w-0">
              <p className="text-sm font-bold">
                {!hasWriting
                  ? '질문과 답변을 채우면 검토를 받을 수 있어요.'
                  : isLoggedIn
                    ? '코치 다섯이 자료를 나눠 분석합니다.'
                    : '검토를 받으려면 로그인이 필요해요.'}
              </p>
              {/* 로그인한 사람에게는 할 말이 아니다 */}
              {!isLoggedIn && (
                <p className="mt-0.5 text-xs break-keep text-slate-400">
                  로그인하면 쓰던 자소서가 그대로 남습니다.
                </p>
              )}
            </div>
          )}
          <div className="flex shrink-0 flex-col-reverse gap-2 sm:ml-auto sm:flex-row sm:items-center">
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
                className="inline-flex h-12 items-center justify-center rounded-2xl bg-blue-600 px-7 text-sm font-bold text-white shadow-[0_8px_24px_-8px_rgba(37,99,235,0.7)] transition-colors duration-200 hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-white/10 disabled:text-white/40 disabled:shadow-none"
                // 바로 넘어가지 않고 제목을 확인한다. 이미 있으면 채워진 채로 뜬다
                disabled={postingBusy}
                onClick={() => openTitleModal('start')}
                type="button"
              >
                문항 쓰러가기 →
              </button>
            ) : (
              <button
                onClick={review}
                disabled={reviewing || registering || saving || !hasWriting}
                className="inline-flex h-12 items-center justify-center rounded-2xl bg-blue-600 px-7 text-sm font-bold text-white shadow-[0_8px_24px_-8px_rgba(37,99,235,0.7)] transition-colors duration-200 hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-white/10 disabled:text-white/40 disabled:shadow-none"
                type="button"
              >
                {registering || reviewing ? <Spinner className="mr-1.5" /> : null}
                {registering ? '공고 분석 중…' : reviewing ? '여는 중…' : 'AI 검토'}
              </button>
            )}
          </div>
        </div>
      </div>

      {titleModal && (
        <TitleDialog
          error={titleError}
          initial={title}
          mode={titleModal}
          onCancel={() => setTitleModal(null)}
          onConfirm={(next) => {
            if (next !== title) {
              setTitle(next);
              touch();
            }
            setTitleModal(null);
            // 넘어가기 직전이면 문항 1로. 쓰던 중에 고친 것이면 그 자리에 머문다
            if (titleModal === 'start') setStep(1);
          }}
        />
      )}
    </section>
  );
}

/**
 * 문항으로 넘어가기 직전에 자소서 이름을 묻는 작은 창.
 *
 * <p>화면 한가운데 띄우고 뒤는 어둡게 누른다. 문서에 바로 붙여(portal) 고정 헤더까지 덮는다 —
 * 이 장은 isolate 라 안에서 z 를 올려도 헤더 아래에 깔린다. 바깥을 눌러 닫지는 않는다
 * (마이페이지 탈퇴 창과 같은 규칙). 닫는 길은 취소와 Esc 다.
 *
 * <p>문항을 쓰다가 제목만 고칠 때(edit)도 같은 창을 쓴다. 고친 값은 창 안에만 들고 있다가
 * 확인할 때 넘긴다 — 취소하면 원래 제목 그대로다. 어느 쪽이든 회사·직무와 쓰던 문항은
 * 건드리지 않는다.
 */
function TitleDialog({
  mode,
  initial,
  error,
  onCancel,
  onConfirm,
}: {
  mode: 'start' | 'edit';
  initial: string;
  error: string | null;
  onCancel: () => void;
  onConfirm: (next: string) => void;
}) {
  const [value, setValue] = useState(initial);
  // 검증에서 돌아온 까닭. 다시 치기 시작하면 그 자리의 이야기가 아니다
  const [shownError, setShownError] = useState(error);
  const ready = value.trim() !== '';

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCancel();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onCancel]);

  return createPortal(
    <div
      aria-labelledby="cl-title-dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 grid place-items-center bg-slate-950/60 px-5 backdrop-blur-sm"
      role="dialog"
    >
      <form
        className="w-full max-w-md rounded-3xl bg-white p-6 text-slate-900 shadow-2xl sm:p-7"
        onSubmit={(event) => {
          event.preventDefault();
          if (ready) onConfirm(value);
        }}
      >
        <h2 className="text-lg font-extrabold tracking-tight" id="cl-title-dialog">
          {mode === 'edit' ? '자기소개서 제목을 수정해주세요.' : '자기소개서 제목을 정해주세요.'}
        </h2>
        <input
          aria-describedby={shownError ? 'cl-title-error' : undefined}
          aria-invalid={shownError ? true : undefined}
          aria-label="제목"
          autoComplete="off"
          autoFocus
          className={`mt-5 h-12 w-full px-4 ${FIELD}`}
          id="cl-title"
          maxLength={MAX_TITLE}
          onChange={(event) => {
            setValue(event.target.value);
            setShownError(null);
          }}
          placeholder="예: 2026 상반기 백엔드 지원"
          value={value}
        />
        {shownError && (
          <p className="mt-2 px-1 text-[13px] font-medium text-rose-600" id="cl-title-error" role="alert">
            {shownError}
          </p>
        )}
        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            className="inline-flex h-11 items-center justify-center rounded-2xl border border-slate-300 px-5 text-sm font-bold text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900"
            onClick={onCancel}
            type="button"
          >
            취소
          </button>
          <button
            className="inline-flex h-11 items-center justify-center rounded-2xl bg-blue-600 px-5 text-sm font-bold text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={!ready}
            type="submit"
          >
            {mode === 'edit' ? '수정하기' : '작성 시작하기 →'}
          </button>
        </div>
      </form>
    </div>,
    document.body,
  );
}

type PostingStatus = 'idle' | 'loading' | 'done' | 'error';

/** 링크가 없을 때 펼치는 칸. null 이면 아무것도 펴지 않았다. */
type AltInput = 'image' | 'file' | 'manual' | null;

/** AI 쪽 OCR 예산(UPLOAD_OCR_MAX_IMAGES)과 맞춘다. 더 받아도 뒤쪽은 읽히지 않는다. */
const MAX_POSTING_IMAGES = 8;

/**
 * 넣을 수 있는 원본 이미지의 합계(QA 단계 프론트 기준). 보낼 때는 띠로 잘라 다시 줄이므로
 * 서버 한도(조각 8MB·요청 20MB)와는 별개다 — 이것은 브라우저가 한꺼번에 들고 있을 양이다.
 */
const MAX_POSTING_UPLOAD_BYTES = 50 * 1024 * 1024;
const MAX_POSTING_UPLOAD_LABEL = '50MB';

/**
 * 채용공고 URL 을 넣고 확인하면 지원 회사와 직무를 대신 채워 준다.
 * 공고 내용은 저장하지 않는다 — 입력칸을 채우고 나면 버린다.
 */
function JobPostingBar({
  alt,
  onAlt,
  onBusyChange,
  onParsed,
}: {
  /** 지금 펼친 대체 입력. 회사·직무 칸(manual)은 바깥에 있어 상태도 바깥이 쥔다 */
  alt: AltInput;
  onAlt: (next: AltInput) => void;
  /** 공고를 읽기 시작하고 끝날 때 알린다. 그동안 부모는 다음 단계로 가는 길을 잠근다 */
  onBusyChange: (busy: boolean) => void;
  onParsed: (
    companyName: string | null,
    positions: string[],
    sourceUrl: string,
    sourceKey: string | null,
  ) => void;
}) {
  const [url, setUrl] = useState('');
  // DB 에 없는 회사의 공고. 이 이름으로 안내 창을 띄우고, 공고 내용은 받지 않는다
  const [unregistered, setUnregistered] = useState<string | null>(null);
  // 이미지를 모으는 칸. 붙여넣기와 파일 고르기는 모이는 곳이 같다
  const imageOpen = alt === 'image' || alt === 'file';
  const pasteZone = useRef<HTMLDivElement>(null);
  const filePicker = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<PostingStatus>('idle');
  const [message, setMessage] = useState('');
  // 자동 인식이 안 되는 것으로 판명난 URL. 같은 주소 재파싱은 성공하지 않으므로 다시 못 누르게 막는다.
  const [blockedUrl, setBlockedUrl] = useState<string | null>(null);
  // 붙여넣은 공고 이미지. 공고는 위에서 아래로 읽히므로 넣은 순서를 지킨다.
  const [images, setImages] = useState<File[]>([]);
  // 넣으려던 이미지를 장수·용량 한도 때문에 받지 못했거나, 이미지로 읽다 실패했을 때의 안내
  const [imageNotice, setImageNotice] = useState<string | null>(null);
  /*
   * 한도 안내는 넘치게 넣으려던 순간의 이야기다. 오래 남겨 두면 8장을 제대로 넣은 사람에게
   * 계속 경고가 떠 있는 것처럼 보여서, 몇 초 뒤에 내린다. 읽기 실패는 다시 누를 때까지 둔다.
   */
  const [noticeFades, setNoticeFades] = useState(false);
  useEffect(() => {
    if (!imageNotice || !noticeFades) return;
    const timer = window.setTimeout(() => setImageNotice(null), 5000);
    return () => window.clearTimeout(timer);
  }, [imageNotice, noticeFades]);
  // 이미지로 공고를 읽는 중. 상태 문구를 주소 칸 아래가 아니라 이미지 칸의 단추 자리에 띄운다
  const [readingImages, setReadingImages] = useState(false);

  const failureText = (error: unknown, fallback: string) => {
    if (error instanceof ApiError && isRateLimited(error)) return '요청이 많습니다. 잠시 후 다시 시도해 주세요.';
    if (error instanceof ApiError && error.status === 413) {
      return '이미지 용량이 너무 큽니다. 장수를 줄이거나 화면을 나눠 캡처해 주세요.';
    }
    return userMessage(error, fallback);
  };
  // 주소로 읽다 실패한 까닭은 주소 칸 아래에 둔다
  const describeFailure = (error: unknown, fallback: string) => {
    setStatus('error');
    setMessage(failureText(error, fallback));
  };

  const urlReady = url.trim() !== '' && url.trim() !== blockedUrl;

  useEffect(() => {
    onBusyChange(status === 'loading');
  }, [status, onBusyChange]);

  /*
   * 읽어 온 공고를 넘기기 전에 회사를 DB 에서 찾아본다. 없으면 회사도 직무도 공고 주소도 받지
   * 않고 안내 창만 띄운다 — 등록되지 않은 회사는 AI 검토가 되지 않아, 채워 두면 끝에 가서야 막힌다.
   * 공고에서 회사명을 못 찾은 경우(null)는 그대로 넘긴다. 회사는 검색칸에서 고르면 된다.
   * 넘겼으면 true.
   */
  const acceptParsed = async (
    companyName: string | null,
    positions: string[],
    sourceUrl: string,
    sourceKey: string | null,
  ) => {
    let registeredName: string | null = null;
    if (companyName) {
      const found = await resolveCompany(companyName);
      if (found.status === 'missing') {
        setUnregistered(companyName);
        return false;
      }
      registeredName = found.name;
    }
    onParsed(registeredName, positions, sourceUrl, sourceKey);
    return true;
  };

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
      const accepted = await acceptParsed(
        result.companyName,
        result.positions,
        result.sourceUrl ?? target,
        result.sourceKey,
      );
      // 잘 됐다는 말은 하지 않는다. 회사·직무 칸이 채워진 것으로 이미 보인다.
      setStatus(accepted ? 'done' : 'idle');
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
    /*
     * 한도 안에 드는 것만 앞에서부터 받는다. 공고는 위에서 아래로 읽히므로 순서를 지키고,
     * 넘치는 것은 버리되 왜 빠졌는지 말한다. 장수가 먼저 차면 용량은 따지지 않는다.
     */
    const next = [...images];
    let total = next.reduce((sum, file) => sum + file.size, 0);
    let notice: string | null = null;
    for (const file of picked) {
      if (next.length >= MAX_POSTING_IMAGES) {
        notice = `이미지는 최대 ${MAX_POSTING_IMAGES}장까지 업로드할 수 있습니다.`;
        break;
      }
      if (total + file.size > MAX_POSTING_UPLOAD_BYTES) {
        notice = `업로드 가능한 총 용량은 최대 ${MAX_POSTING_UPLOAD_LABEL}입니다.`;
        continue;
      }
      next.push(file);
      total += file.size;
    }
    setImages(next);
    setImageNotice(notice);
    setNoticeFades(notice !== null);
    // 주소 칸에 붙여넣었으면 이미지 칸을 대신 편다. 이미 폈으면 그대로 둔다
    if (!imageOpen) onAlt('image');
    if (status === 'error') {
      setStatus('idle');
      setMessage('');
    }
  };

  /*
   * 조각 수("조각 8개")는 더 말하지 않는다. 보낼 때 띠로 자르는 것은 안쪽 사정이라, 사용자가
   * 넣은 것(이미지 N장)으로만 말한다. 기다리는 동안은 단추 자리가 그 문구로 바뀐다.
   */
  const confirmImages = async () => {
    if (images.length === 0) return;
    setStatus('loading');
    setMessage('');
    setImageNotice(null);
    setReadingImages(true);
    const failImages = (text: string) => {
      setStatus('idle');
      setImageNotice(text);
      setNoticeFades(false);
    };
    try {
      // 전체 페이지 캡처는 세로가 아주 길다. 통째로 보내면 프록시가 413 으로 끊으므로
      // 여기서 띠 모양으로 잘라 조각마다 JPEG 로 줄인다.
      const prepared = await preparePostingImages(images);
      const total = prepared.reduce((sum, file) => sum + file.size, 0);
      if (
        total > MAX_POSTING_IMAGES_BYTES ||
        prepared.some((file) => file.size > MAX_POSTING_IMAGE_BYTES)
      ) {
        failImages('이미지 용량이 너무 큽니다. 공고를 나눠 캡처해 주세요.');
        return;
      }
      const result = await parseJobPostingImages(prepared);
      const accepted = await acceptParsed(
        result.companyName,
        result.positions,
        result.sourceUrl ?? '',
        result.sourceKey,
      );
      if (!accepted) {
        setStatus('idle');
        return;
      }
      setStatus('done');
      setImages([]);
    } catch (error) {
      failImages(failureText(error, '이미지에서 공고를 읽지 못했습니다.'));
    } finally {
      setReadingImages(false);
    }
  };

  /*
   * 링크가 없을 때의 길. 다음 단계로 가는 단추(아래 CTA)가 아니라 입력 방식을 고르는 것이라
   * 모양을 갈랐다 — 낮은 알약에 글자만큼의 폭, 보통 굵기. CTA 는 높은 모서리 사각에 굵은 글자다.
   * 누른 것만 파란 테두리·옅은 파란 바탕으로 남겨 지금 어느 길에 있는지 보인다(채운 파랑은 쓰지 않는다).
   */
  const altButton = (active: boolean) =>
    `inline-flex h-9 items-center gap-2 rounded-full border px-5 text-[14px] font-medium whitespace-nowrap transition-colors duration-200 ${
      active
        ? 'border-blue-400/80 bg-blue-500/10 text-white'
        : 'border-white/15 bg-transparent text-slate-300 hover:border-white/25 hover:bg-white/[0.06] hover:text-white'
    }`;

  return (
    <div>
      {/*
        기업 분석 검색칸과 같은 모양이다 — 알약 칸 안에 아이콘·입력·단추를 한 줄로 세운다.
        라벨과 아래 도움말은 걷었다. 제목 밑 설명이 같은 말을 이미 한다.
        주소 칸에 이미지를 붙여넣어도 이미지 칸으로 넘긴다.
      */}
      {/* 본문(896px)을 다 채우면 좌우로 퍼져 보여 780px 로 줄이고 가운데에 둔다. 아래 펼쳐지는 칸(이미지·회사·직무)도 같은 폭이다 */}
      <div className="mx-auto w-full max-w-[780px]">
      <div className="flex items-center gap-2 rounded-full border border-slate-300 bg-white p-2 shadow-sm transition sm:gap-3">
        <LinkIcon className="ml-2 size-5 text-slate-400 sm:ml-3" />
        <input
          id="cl-posting-url"
          // 백엔드 JobPostingParseRequest 의 @Size(max=2000) 과 같은 값
          maxLength={2000}
          aria-label="채용공고 URL (선택)"
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
          onPaste={(event) => {
            const pasted = Array.from(event.clipboardData.files);
            if (!pasted.some((file) => file.type.startsWith('image/'))) return;
            event.preventDefault();
            addImages(pasted);
          }}
          type="url"
          inputMode="url"
          /*
           * 입력하면 칸 안에 파란 네모가 생기던 것은 브라우저 자동완성(:autofill) 배경이다.
           * 자동완성을 끄고, 그래도 채워지면 흰 그림자로 덮어 배경을 흰색 그대로 둔다.
           */
          autoComplete="off"
          placeholder="https://recruit.example.com/..."
          className="h-10 min-w-0 flex-1 bg-transparent text-base text-slate-900 outline-none placeholder:text-slate-400 autofill:shadow-[inset_0_0_0_1000px_#fff] autofill:[-webkit-text-fill-color:#0f172a]"
        />
        {/*
          칸 안의 단추다. 검색칸의 '검색' 과 같은 크기·모양으로 두어 칸이 주인공이 되게 한다.
          좁은 화면에서는 "불러오기" 만 남긴다 — 단추가 칸을 먹어 들어가면 주소가 안 보인다.
        */}
        <button
          aria-label="공고 불러오기"
          onClick={confirmUrl}
          disabled={status === 'loading' || !urlReady}
          className="inline-flex shrink-0 items-center gap-1 rounded-full bg-blue-600 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:bg-slate-300"
          type="button"
        >
          {/* 이미지로 읽는 동안에는 이 단추는 잠기기만 한다 — 돌아가는 것은 아래 이미지 칸이다 */}
          {status === 'loading' && !readingImages ? (
            <>
              <Spinner />
              불러오는 중…
            </>
          ) : (
            <>
              <span className="hidden sm:inline">공고</span> 불러오기
              <span aria-hidden="true">→</span>
            </>
          )}
        </button>
      </div>

      <p
        className={[
          message ? 'mt-2 text-[13px] font-medium break-keep' : 'sr-only',
          status === 'error' ? 'text-amber-300' : 'text-slate-300',
        ].join(' ')}
        role={status === 'error' ? 'alert' : 'status'}
      >
        {message}
      </p>
      </div>

      {/*
        링크가 없을 때의 길 셋. 본문이 이미지뿐이라 주소로는 못 읽는 공고도 여기로 온다.
        주소 칸 바로 밑 가운데에 모아 주소 칸의 딸린 길로 읽히게 한다. 안내 문구는 단추보다
        옅게 두되 읽히게 한다 — 눈이 먼저 가야 하는 것은 단추다. 자리가 모자라면 줄을 바꾼다.
      */}
      <div className="mt-8 flex flex-col items-center">
        <p className="mb-3 text-center text-[14px] font-medium text-slate-400">공고 링크가 없나요?</p>
        <div className="flex flex-wrap justify-center gap-3">
          <button
            aria-expanded={alt === 'image'}
            aria-pressed={alt === 'image'}
            className={altButton(alt === 'image')}
            onClick={() => {
              if (alt === 'image') {
                onAlt(null);
                return;
              }
              onAlt('image');
              // 펼친 칸이 그려진 뒤라야 붙여넣을 자리를 잡아 줄 수 있다
              requestAnimationFrame(() => pasteZone.current?.focus());
            }}
            type="button"
          >
            <ImageIcon className="size-4" />
            이미지 업로드
          </button>
          <button
            aria-expanded={alt === 'file'}
            aria-pressed={alt === 'file'}
            className={altButton(alt === 'file')}
            onClick={() => {
              if (alt === 'file') {
                onAlt(null);
                return;
              }
              onAlt('file');
              filePicker.current?.click();
            }}
            type="button"
          >
            <UploadIcon className="size-4" />
            파일 업로드
          </button>
          <button
            aria-expanded={alt === 'manual'}
            aria-pressed={alt === 'manual'}
            className={altButton(alt === 'manual')}
            onClick={() => onAlt(alt === 'manual' ? null : 'manual')}
            type="button"
          >
            <PencilIcon className="size-4" />
            직접 입력
          </button>
        </div>
        <input
          ref={filePicker}
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
      </div>

      {/*
        붙여넣기·불러오기 둘 다 여기에 모인다. 몇 장까지 되는지는 넣기 전에 알아야 한다.
        용량은 숫자로 못 박지 않는다 — 보낼 때 띠로 잘라 다시 줄이므로 원본 크기로는 말할 수 없다.
      */}
      {imageOpen && (
        <div className="mx-auto mt-3 w-full max-w-[780px] rounded-3xl bg-white p-4 text-slate-800 shadow-sm">
          <div
            ref={pasteZone}
            className="flex min-h-[60px] min-w-0 items-center justify-center rounded-2xl border border-dashed border-slate-300 px-3 py-2.5 outline-none"
            onClick={() => {
              if (alt === 'file' && images.length === 0) filePicker.current?.click();
            }}
            onPaste={(event) => {
              const pasted = Array.from(event.clipboardData.files);
              if (!pasted.some((file) => file.type.startsWith('image/'))) return;
              event.preventDefault();
              addImages(pasted);
            }}
            tabIndex={0}
          >
            {images.length === 0 ? (
              <span className="text-center text-[13.5px] text-slate-400">
                {alt === 'file' ? (
                  '여기를 눌러 공고 이미지를 고르세요'
                ) : (
                  <>
                    공고 캡처를 <kbd className="rounded bg-slate-100 px-1">Ctrl</kbd>+
                    <kbd className="rounded bg-slate-100 px-1">V</kbd> 로 붙여넣으세요
                  </>
                )}
              </span>
            ) : (
              <div className="flex w-full min-w-0 flex-wrap items-center gap-1.5">
                {images.map((image, index) => (
                  /*
                    넣은 파일의 이름 그대로 보인다(내가 저장한 파일명.png). 붙여넣은 캡처는 브라우저가
                    image.png 라고 이름을 붙여 주고, 이름이 없으면 같은 이름을 쓴다. 긴 이름은 줄여
                    보이고 마우스를 올리면 다 보인다.
                  */
                  <span
                    key={`${image.name}-${index}`}
                    className="inline-flex max-w-full min-w-0 items-center gap-1 rounded-full bg-slate-100 py-0.5 pr-1 pl-2.5 text-[12px] font-medium text-slate-600"
                    title={image.name || 'image.png'}
                  >
                    <span className="max-w-[220px] truncate">{image.name || 'image.png'}</span>
                    <button
                      aria-label={`${index + 1}번 이미지 빼기`}
                      className="flex size-5 items-center justify-center rounded-full text-slate-400 transition-colors hover:bg-slate-200 hover:text-slate-700"
                      onClick={() => {
                        setImages((prev) => prev.filter((_, at) => at !== index));
                        setImageNotice(null);
                      }}
                      type="button"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
          {/*
            왼쪽은 늘 보이는 안내(옅은 회색), 오른쪽은 할 일. 읽기 시작하면 단추 자리가 그대로
            "읽고 있어요" 로 바뀐다 — 방금 누른 것이 돌아가고 있다는 것이 그 자리에서 보인다.
          */}
          <div className="mt-3 flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
            <p className="text-[12.5px] text-slate-400">
              최대 {MAX_POSTING_IMAGES}장 · 최대 {MAX_POSTING_UPLOAD_LABEL}
            </p>
            {readingImages ? (
              <p className="ml-auto text-[13px] font-semibold break-keep text-blue-600" role="status">
                이미지 {images.length}장을 확인했어요. 공고 정보를 읽고 있어요
                <LoadingDots />
              </p>
            ) : (
              images.length > 0 && (
                <button
                  className="ml-auto inline-flex h-10 shrink-0 items-center gap-2 rounded-2xl bg-blue-600 px-4 text-[13px] font-semibold text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                  disabled={status === 'loading'}
                  onClick={confirmImages}
                  type="button"
                >
                  <SendIcon />
                  이미지 {images.length}장 확인하기
                </button>
              )
            )}
          </div>
          {/* 넘치게 넣으려 했거나 읽다 실패했을 때만. 진한 빨강 대신 옅은 산호색으로 */}
          {imageNotice && (
            <p className="mt-2 text-[12.5px] font-medium text-[#d66b6b]" role="alert">
              {imageNotice}
            </p>
          )}
        </div>
      )}

      {unregistered && (
        <NoticeDialog onClose={() => setUnregistered(null)} title="아직 등록되지 않은 기업이에요">
          <b className="font-semibold text-slate-900">{unregistered}</b> 은(는) Fit 에 등록되지 않은 기업이라
          이 공고로는 AI 검토를 할 수 없어요. 다른 공고를 넣거나, 직접 입력에서 등록된 기업을 골라 주세요.
        </NoticeDialog>
      )}
    </div>
  );
}

/**
 * 확인 하나만 있는 안내 창. 제목 창과 같은 판(흰 판·둥근 모서리·뒤를 누르는 막)을 쓰고,
 * 문서에 바로 붙여 고정 헤더까지 덮는다. Esc 로도 닫힌다.
 */
function NoticeDialog({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return createPortal(
    <div
      aria-describedby="cl-notice-body"
      aria-labelledby="cl-notice-title"
      aria-modal="true"
      className="fixed inset-0 z-50 grid place-items-center bg-slate-950/60 px-5 backdrop-blur-sm"
      role="alertdialog"
    >
      <div className="w-full max-w-md rounded-3xl bg-white p-6 text-slate-900 shadow-2xl sm:p-7">
        <h2 className="text-lg font-extrabold tracking-tight" id="cl-notice-title">
          {title}
        </h2>
        <p className="mt-3 text-[14px] leading-6 break-keep text-slate-600" id="cl-notice-body">
          {children}
        </p>
        <div className="mt-6 flex justify-end">
          <button
            autoFocus
            className="inline-flex h-11 items-center justify-center rounded-2xl bg-blue-600 px-6 text-sm font-bold text-white transition-colors hover:bg-blue-700"
            onClick={onClose}
            type="button"
          >
            확인
          </button>
        </div>
      </div>
    </div>,
    document.body,
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
  /*
   * 기본 <select> 는 펼친 목록을 운영체제가 그려서 각진 회색 네모로 떴다. 알약 칸 아래
   * 둥근 목록(지원 회사 검색 결과와 같은 모양)을 직접 편다. 포커스는 단추에 둔 채
   * 위아래 화살표로 옮기고 Enter 로 고른다. 맨 끝은 '직접 입력' 이다.
   */
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const root = useRef<HTMLDivElement>(null);
  const options = [...choices, TYPE_INSTEAD];
  const listId = 'cl-position-list';

  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  const pick = (value: string) => {
    setOpen(false);
    if (value === TYPE_INSTEAD) onTypeInstead();
    else onSelect(value);
  };

  const openList = () => {
    setActive(Math.max(0, choices.indexOf(selected)));
    setOpen(true);
  };

  return (
    <div className="relative" ref={root}>
      <button
        aria-activedescendant={open && active >= 0 ? `${listId}-${active}` : undefined}
        aria-controls={listId}
        aria-expanded={open}
        aria-haspopup="listbox"
        className="flex h-12 w-full items-center justify-between gap-2 rounded-full border border-slate-300 bg-white pr-4 pl-5 text-left text-[15px] transition-colors hover:border-slate-400 focus:outline-none"
        id="cl-position"
        onClick={() => (open ? setOpen(false) : openList())}
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            setOpen(false);
            return;
          }
          if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault();
            if (!open) {
              openList();
              return;
            }
            const step = event.key === 'ArrowDown' ? 1 : -1;
            setActive((at) => (at + step + options.length) % options.length);
            return;
          }
          if ((event.key === 'Enter' || event.key === ' ') && open && active >= 0) {
            event.preventDefault();
            pick(options[active]);
          }
        }}
        type="button"
      >
        <span className={`truncate ${selected ? 'text-slate-900' : 'text-slate-400'}`}>
          {selected || '직무를 고르세요'}
        </span>
        <svg
          aria-hidden="true"
          className={`size-4 shrink-0 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          viewBox="0 0 24 24"
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>

      {open && (
        <div className="absolute top-full left-0 z-20 mt-2 w-full overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-[0_12px_32px_-16px_rgba(15,23,42,0.28)]">
          <ul
            aria-label="공고에서 찾은 직무"
            className="max-h-[280px] overflow-y-auto overscroll-contain p-1.5"
            id={listId}
            role="listbox"
          >
            {options.map((option, index) => {
              const typing = option === TYPE_INSTEAD;
              const chosen = !typing && option === selected;
              return (
                <li
                  aria-selected={chosen}
                  className={`flex cursor-pointer items-center justify-between gap-2 rounded-xl px-3 py-2.5 text-[14px] transition-colors ${
                    typing ? 'mt-1 border-t border-slate-100 text-slate-500' : chosen ? 'font-semibold text-blue-700' : 'text-slate-700'
                  } ${index === active ? 'bg-slate-100' : chosen ? 'bg-blue-50' : 'hover:bg-slate-50'}`}
                  id={`${listId}-${index}`}
                  key={option}
                  // 누르는 순간 단추가 포커스를 잃어 목록이 먼저 닫히지 않게 한다
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => pick(option)}
                  onMouseEnter={() => setActive(index)}
                  role="option"
                >
                  <span className="min-w-0 truncate">{typing ? '+ 직접 입력' : option}</span>
                  {chosen && <span aria-hidden="true">✓</span>}
                </li>
              );
            })}
          </ul>
        </div>
      )}
      <p className="mt-1.5 pl-1 text-[12px] text-slate-400">공고에서 직무 {choices.length}개를 찾았어요.</p>
    </div>
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
        className="inline-flex h-12 w-full items-center justify-center rounded-2xl border border-white/25 bg-white/[0.04] px-6 text-sm font-bold text-slate-200 transition-colors duration-200 hover:border-white/40 hover:bg-white/10 hover:text-white disabled:opacity-40 sm:w-auto"
        type="button"
      >
        {saving ? <Spinner className="mr-1.5" /> : null}
        {saving ? '이동 중…' : '로그인하고 저장'}
      </button>
    );
  }

  return (
    <div className="flex flex-col-reverse items-center gap-2 sm:flex-row">
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
        className="inline-flex h-12 w-full items-center justify-center rounded-2xl border border-white/25 bg-white/[0.04] px-6 text-sm font-bold text-slate-200 transition-colors duration-200 hover:border-white/40 hover:bg-white/10 hover:text-white disabled:opacity-40 sm:w-auto disabled:cursor-not-allowed"
        type="button"
      >
        {saving ? <Spinner className="mr-1.5" /> : null}
        {saving ? '저장 중…' : '저장'}
      </button>
    </div>
  );
}

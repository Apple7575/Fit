import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CharacterSlot } from '../../components/brand/CharacterSlot';
import { PersonMark } from '../../components/brand/MediaSlot';
import { prefersReducedMotion, useInView } from '../../hooks/useInView';

/** 모의 면접 화면과 같은 영상 */
const HERO_VIDEO = '/interview-media/hero.mp4';
const HERO_POSTER = '/interview-media/hero.jpg';

const QUESTIONS = [
  {
    tag: '회사 데이터',
    q: 'DS 부문이 파운드리 투자를 늘리는 상황에서, 지원자가 기여할 수 있는 지점은 무엇인가요?',
  },
  {
    tag: '자소서 기반',
    q: '자소서에 쓴 공정 데이터 분석 경험에서 가장 어려웠던 판단은 무엇이었나요?',
  },
  { tag: '추가 질문', q: '그 판단이 틀렸다면 어떻게 알아챘을 것 같나요?' },
];

const FEEDBACK = [
  { kind: 'STRENGTH', cat: '구체성', text: '수치(불량률 3.2%→1.1%)로 결과를 말해 설득력이 있음' },
  { kind: 'STRENGTH', cat: '기업직무이해', text: 'DS 투자 방향과 본인 경험을 연결한 점' },
  { kind: 'IMPROVEMENT', cat: '전달력', text: '첫 20초에 결론을 먼저 말하면 더 또렷해짐' },
] as const;

/**
 * REC 는 계속 떠 있다. 다만 못 박아 두면 그림이 되므로 5초마다 잠깐 껐다 켠다 —
 * 실제로 녹화 중인 화면처럼 시간이 흐르는 것이 보인다.
 */
const REC_ON_MS = 5000;
const REC_OFF_MS = 450;

const TYPE_MS = 28;
const ANSWER_MS = 3200;
const FEEDBACK_MS = 2600;
const REST_MS = 3000;

type Phase = 'question' | 'answer' | 'feedback';

/**
 * AI 모의 면접 소개. 오른쪽은 실제 면접 화면을 축소한 목업이 자동으로 한 바퀴 돈다.
 * 질문이 타자처럼 찍힘 → 답변 녹음(타이머·받아쓰기 막대) → 강점·개선점이 하나씩 뜸.
 */
export function InterviewDemo() {
  const [ref, inView] = useInView<HTMLElement>({ threshold: 0.4, once: false });
  const reduce = prefersReducedMotion();
  const [qi, setQi] = useState(0);
  const [typed, setTyped] = useState(reduce ? QUESTIONS[0].q.length : 0);
  const [phase, setPhase] = useState<Phase>(reduce ? 'feedback' : 'question');
  const [seconds, setSeconds] = useState(0);
  const [shownFeedback, setShownFeedback] = useState(reduce ? FEEDBACK.length : 0);
  // 녹화 표시는 데모 단계와 따로 돈다. 질문을 읽는 동안에도 화면은 녹화 중이다
  const [recOn, setRecOn] = useState(true);
  const [recSeconds, setRecSeconds] = useState(0);

  useEffect(() => {
    if (reduce || !inView) return;
    let timer: number;

    if (!recOn) {
      timer = window.setTimeout(() => {
        setRecSeconds(0);
        setRecOn(true);
      }, REC_OFF_MS);
    } else if (recSeconds * 1000 < REC_ON_MS) {
      timer = window.setTimeout(() => setRecSeconds((s) => s + 1), 1000);
    } else {
      // 5초를 다 세면 곧바로 끈다. 0ms 인 것은 effect 안에서 바로 setState 하지 않기 위해서다
      timer = window.setTimeout(() => setRecOn(false), 0);
    }

    return () => window.clearTimeout(timer);
  }, [inView, reduce, recOn, recSeconds]);

  useEffect(() => {
    if (reduce || !inView) return;
    let cancelled = false;
    let timer: number;
    const question = QUESTIONS[qi].q;

    const run = () => {
      if (cancelled) return;
      if (phase === 'question') {
        if (typed < question.length) {
          timer = window.setTimeout(() => setTyped((t) => t + 1), TYPE_MS);
        } else {
          timer = window.setTimeout(() => {
            setSeconds(0);
            setPhase('answer');
          }, 700);
        }
      } else if (phase === 'answer') {
        if (seconds * 1000 < ANSWER_MS) {
          timer = window.setTimeout(() => setSeconds((s) => s + 1), 1000);
        } else {
          setShownFeedback(0);
          setPhase('feedback');
        }
      } else {
        if (shownFeedback < FEEDBACK.length) {
          timer = window.setTimeout(
            () => setShownFeedback((n) => n + 1),
            FEEDBACK_MS / FEEDBACK.length,
          );
        } else {
          timer = window.setTimeout(() => {
            setQi((i) => (i + 1) % QUESTIONS.length);
            setTyped(0);
            setPhase('question');
          }, REST_MS);
        }
      }
    };
    run();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [inView, reduce, phase, typed, seconds, shownFeedback, qi]);

  const current = QUESTIONS[qi];
  const mm = String(Math.floor(recSeconds / 60)).padStart(2, '0');
  const ss = String(recSeconds % 60).padStart(2, '0');

  return (
    <section
      aria-labelledby="interview-title"
      className="relative isolate snap-start flex min-h-screen items-center overflow-hidden bg-slate-950 pt-14 text-white"
      id="interview"
      ref={ref}
    >
      {/* 모의 면접 화면이 쓰는 영상 그대로. 빈 의자가 이 구획의 뜻을 그대로 말한다 */}
      <div aria-hidden="true" className="absolute inset-0">
        <video
          autoPlay
          className="size-full object-cover"
          loop
          muted
          playsInline
          poster={HERO_POSTER}
          preload="metadata"
          src={HERO_VIDEO}
        />
        <div className="absolute inset-0 bg-gradient-to-br from-slate-950/88 via-slate-950/78 to-slate-950/92" />
      </div>

      <div className="relative mx-auto grid w-full max-w-[1200px] items-center gap-12 px-6 py-16 lg:grid-cols-[1.1fr_1fr]">
        {/* 면접 화면 목업 */}
        <div
          aria-label="모의 면접 화면 예시"
          className="order-2 grid gap-4 lg:order-1 lg:grid-cols-[1.1fr_1fr]"
          role="img"
        >
          {/*
            "▶ 면접 화면 클립" 이름표는 걷었다. 누를 수 없는 그림인데 재생 단추처럼 보였다.
            그 자리에는 정작 사람들이 궁금해하는 말(영상을 저장하지 않는다)을 세운다.
          */}
          <div
            aria-label="면접 화면 자리"
            /*
             * 가운데보다 살짝 아래에 세운다 — 위쪽 REC 딱지와 무게를 맞추면 아래 여백만 넓어
             * 보였다. px 로 밀면 화면이 좁아질 때 타일이 커지면서 너무 내려가므로 타일 너비에
             * 비례하는 % 로 민다.
             */
            className="relative flex aspect-video flex-col items-center justify-center gap-3 overflow-hidden rounded-[var(--radius-card)] bg-slate-900 pt-[5%] ring-1 ring-white/15"
            role="img"
          >
            <PersonMark />
            <span className="rounded-full bg-black/50 px-2.5 py-1 text-[11px] font-semibold text-white/90 backdrop-blur">
              🎥 영상은 저장되지 않습니다 · 답변 텍스트만 분석
            </span>
            {recOn && (
              <span className="absolute left-3 top-3 inline-flex items-center gap-1.5 rounded-full bg-rose-600 px-2.5 py-1 text-xs font-bold text-white">
                <span className="size-2 animate-pulse rounded-full bg-white" /> REC {mm}:{ss}
              </span>
            )}
          </div>
          <div className="flex flex-col gap-3 rounded-[var(--radius-card)] bg-white p-4 text-slate-900 ring-1 ring-white/10">
            <div className="flex items-center gap-2 text-xs font-bold text-slate-500">
              <span className="rounded-full bg-blue-50 px-2 py-0.5 text-blue-700">Q{qi + 1}</span>
              <span className="rounded-full bg-slate-100 px-2 py-0.5">{current.tag}</span>
              <span className="ml-auto flex gap-1">
                {QUESTIONS.map((_, i) => (
                  <span
                    className={`h-1.5 rounded-full ${i === qi ? 'w-5 bg-blue-600' : i < qi ? 'w-1.5 bg-blue-200' : 'w-1.5 bg-slate-200'}`}
                    key={i}
                  />
                ))}
              </span>
            </div>
            <p className="min-h-[3.4em] text-sm font-semibold leading-snug text-slate-900">
              {current.q.slice(0, typed)}
              {phase === 'question' && typed < current.q.length && (
                <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-blue-600 align-middle" />
              )}
            </p>
            <div className="rounded-xl bg-slate-50 p-3">
              <p className="mb-1.5 text-[11px] font-bold text-slate-400">답변 트랜스크립트</p>
              {phase === 'answer' ? (
                <div className="space-y-1.5">
                  {[92, 76, 58].map((w, i) => (
                    <span
                      className="block h-2 rounded-full bg-slate-200"
                      key={i}
                      style={{
                        width: `${Math.min(w, (seconds + 1) * 33)}%`,
                        transition: 'width 0.9s ease',
                      }}
                    />
                  ))}
                </div>
              ) : phase === 'feedback' ? (
                <p className="text-xs leading-relaxed text-slate-600">
                  불량률을 3.2%에서 1.1%로 낮춘 공정 데이터 분석 경험이 있습니다. DS 부문이 파운드리
                  수율을 올리는 데 같은 방식으로…
                </p>
              ) : (
                <p className="text-xs text-slate-400">
                  녹화를 시작하면 말한 내용이 여기에 받아써집니다.
                </p>
              )}
            </div>
            <ul className="space-y-1.5" aria-label="AI 피드백">
              {FEEDBACK.slice(0, shownFeedback).map((f) => (
                <li
                  className={`anim-pop flex items-start gap-2 rounded-lg px-2.5 py-1.5 text-xs ${
                    f.kind === 'STRENGTH'
                      ? 'bg-emerald-50 text-emerald-900'
                      : 'bg-amber-50 text-amber-900'
                  }`}
                  key={f.text}
                >
                  <span className="shrink-0 font-bold">
                    {f.kind === 'STRENGTH' ? '강점' : '개선점'}
                  </span>
                  <span className="shrink-0 text-slate-500">{f.cat}</span>
                  <span>{f.text}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="order-1 lg:order-2">
          <p className="mb-3 text-sm font-bold uppercase tracking-[0.2em] text-blue-300">
            AI interview
          </p>
          <h2 className="display-lg text-balance" id="interview-title">
            실제 면접관처럼
            <br />
            묻고, 들어줍니다.
          </h2>
          {/* 첫 장과 같이, 한글이 단어 한가운데서 끊기지 않게 띄어쓰기에서만 줄을 바꾼다 */}
          <p className="body-lg mt-5 max-w-[40ch] break-keep text-slate-300">
            질문을 던지면 말로 답하고, 강점과 개선점을 정리해 줍니다.
          </p>
          <div className="mt-8 flex items-end gap-3">
            <CharacterSlot character="owl" size={72} />
            <p className="rounded-2xl bg-white/10 px-4 py-3 text-sm font-semibold text-white ring-1 ring-white/15">
              백엔드 지원자라면 장애 대응부터 물어볼 거예요.
            </p>
          </div>
          <Link
            className="mt-8 inline-flex items-center gap-1 rounded-full bg-white px-6 py-3 text-sm font-bold text-slate-950 transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-lift)]"
            to="/interviews"
          >
            모의 면접 시작 <span aria-hidden="true">›</span>
          </Link>
        </div>
      </div>
    </section>
  );
}

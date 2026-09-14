import { useEffect, useRef, useState } from 'react';
import { requestFollowup } from './api';
import { useSpeech, useWebcam } from './hooks';
import { SOURCE_BADGE } from './styles';
import type { Followup, GeneratedQuestion, InterviewConfig, SessionItem } from './types';

interface InterviewSessionProps {
  config: InterviewConfig;
  questions: GeneratedQuestion[];
  onFinish: (items: SessionItem[]) => void;
  onExit: () => void;
}

type Phase = 'ready' | 'prep' | 'recording' | 'reviewing';

const PREP_SECONDS = 3;

/** 영상 면접 진행. 문항별 웹캠 녹화 + 실시간 STT. 답변 후 옵션으로 꼬리질문을 받는다. 영상은 저장하지 않는다. */
export function InterviewSession({ config, questions, onFinish, onExit }: InterviewSessionProps) {
  const { videoRef, status } = useWebcam();
  const speech = useSpeech();

  const [queue, setQueue] = useState<SessionItem[]>(() =>
    questions.map((q) => ({ question: q.question, sourceType: q.sourceType, transcript: '', isFollowup: false })),
  );
  const [idx, setIdx] = useState(0);
  const [phase, setPhase] = useState<Phase>('ready');
  const [prep, setPrep] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [fup, setFup] = useState<Followup | null>(null);
  const [fupLoading, setFupLoading] = useState(false);
  const followed = useRef<Set<number>>(new Set());
  const timerRef = useRef<number | null>(null);

  const current = queue[idx];
  const isLast = idx + 1 >= queue.length;
  const badge = SOURCE_BADGE[current.sourceType];

  const setTranscript = (text: string) =>
    setQueue((prev) => prev.map((item, i) => (i === idx ? { ...item, transcript: text } : item)));

  // 준비 카운트다운
  useEffect(() => {
    if (phase !== 'prep') return;
    if (prep <= 0) {
      beginRecording();
      return;
    }
    const t = window.setTimeout(() => setPrep((p) => p - 1), 1000);
    return () => window.clearTimeout(t);
    // beginRecording 은 최신 idx 를 클로저로 참조하므로 의존성에 넣지 않는다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, prep]);

  useEffect(() => () => stopTimer(), []);

  const stopTimer = () => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const startPrep = () => {
    setFup(null);
    setPrep(PREP_SECONDS);
    setPhase('prep');
  };

  const beginRecording = () => {
    setElapsed(0);
    setPhase('recording');
    timerRef.current = window.setInterval(() => setElapsed((e) => e + 1), 1000);
    speech.start(setTranscript);
  };

  const stopRecording = async () => {
    stopTimer();
    speech.stop();
    setPhase('reviewing');
    const answer = queue[idx].transcript.trim();
    if (config.followupEnabled && !current.isFollowup && answer.length > 0 && !followed.current.has(idx)) {
      setFupLoading(true);
      try {
        const followup = await requestFollowup({
          question: current.question,
          transcript: answer,
          targetPosition: config.targetPosition,
        });
        setFup(followup);
      } catch {
        setFup(null);
      } finally {
        setFupLoading(false);
      }
    }
  };

  const askFollowup = () => {
    if (!fup) return;
    followed.current.add(idx);
    const item: SessionItem = { question: fup.question, sourceType: 'followup', transcript: '', isFollowup: true };
    setQueue((prev) => {
      const next = prev.slice();
      next.splice(idx + 1, 0, item);
      return next;
    });
    setFup(null);
    setIdx(idx + 1);
    setPhase('ready');
  };

  const next = () => {
    setFup(null);
    if (isLast) {
      onFinish(queue);
    } else {
      setIdx(idx + 1);
      setPhase('ready');
    }
  };

  const mmss = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

  return (
    <div className="mx-auto max-w-6xl px-6 py-6">
      <div className="mb-4 flex items-center justify-between">
        <button onClick={onExit} type="button" className="text-sm text-slate-400 hover:text-slate-600">
          ← 나가기
        </button>
        <div className="flex items-center gap-1.5">
          {queue.map((item, i) => (
            <div
              key={i}
              className={`h-1.5 rounded-full transition-all ${
                i === idx
                  ? item.isFollowup
                    ? 'w-8 bg-rose-500'
                    : 'w-8 bg-blue-600'
                  : i < idx
                    ? 'w-4 bg-blue-300'
                    : 'w-4 bg-slate-200'
              }`}
            />
          ))}
        </div>
        <span className="text-sm font-medium text-slate-500">
          {idx + 1} / {queue.length}
        </span>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.1fr_1fr]">
        {/* 웹캠 */}
        <div className="overflow-hidden rounded-2xl bg-slate-900 shadow-sm">
          <div className="relative aspect-video">
            <video
              ref={videoRef}
              muted
              playsInline
              className="h-full w-full object-cover"
              style={{ transform: 'scaleX(-1)' }}
            />
            {status === 'denied' && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-center text-slate-300">
                <div className="text-4xl">📷</div>
                <p className="text-sm">
                  카메라 권한이 필요합니다.
                  <br />
                  브라우저 주소창의 카메라 아이콘에서 허용해 주세요.
                </p>
              </div>
            )}
            {phase === 'recording' && (
              <div className="absolute top-3 left-3 flex items-center gap-1.5 rounded-full bg-rose-600/90 px-2.5 py-1 text-xs font-semibold text-white">
                <span className="h-2 w-2 animate-pulse rounded-full bg-white" /> REC {mmss(elapsed)}
              </div>
            )}
            {phase === 'prep' && (
              <div className="absolute inset-0 flex items-center justify-center bg-slate-900/70">
                <div className="text-center text-white">
                  <div className="text-6xl font-bold">{prep}</div>
                  <p className="mt-2 text-sm text-slate-300">잠시 후 녹화가 시작됩니다</p>
                </div>
              </div>
            )}
          </div>
          <div className="flex items-center justify-between px-4 py-2 text-xs text-slate-400">
            <span>🎥 영상은 저장되지 않습니다 · 답변 텍스트만 분석에 사용됩니다</span>
            <span>{speech.supported ? '🎙 실시간 음성인식' : '🎙 음성인식 미지원 — 직접 입력'}</span>
          </div>
        </div>

        {/* 질문 + 답변 */}
        <div className="flex flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-slate-300">Q{idx + 1}</span>
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ${badge.className}`}>
              {badge.label}
            </span>
          </div>
          <p className="mt-2 text-lg font-semibold leading-7 text-slate-800">{current.question}</p>
          {current.isFollowup && (
            <p className="mt-1 text-xs text-rose-500">↳ 직전 답변을 듣고 면접관이 드리는 추가 질문입니다.</p>
          )}

          <div className="mt-4 flex-1">
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">답변 트랜스크립트</span>
              {phase === 'reviewing' && <span className="text-xs text-slate-400">직접 수정할 수 있어요</span>}
            </div>
            <textarea
              value={current.transcript}
              onChange={(e) => setTranscript(e.target.value)}
              readOnly={phase === 'recording'}
              placeholder={
                phase === 'recording'
                  ? '말씀하시면 여기에 받아써집니다…'
                  : '녹화를 시작하면 답변이 자동으로 기록됩니다.'
              }
              className="h-36 w-full resize-none rounded-lg border border-slate-200 bg-slate-50 p-3 text-[14px] leading-6 text-slate-700 outline-none focus:border-blue-300 focus:bg-white"
            />
          </div>

          {phase === 'reviewing' && fupLoading && (
            <p className="mt-3 text-xs text-slate-400">면접관이 추가 질문을 준비 중…</p>
          )}

          {phase === 'reviewing' && fup && (
            <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50/70 p-3">
              <div className="mb-1 text-[11px] font-semibold text-rose-600">🎙 면접관의 추가 질문</div>
              <p className="text-[14px] leading-6 font-medium text-slate-800">{fup.question}</p>
              {fup.basis && <p className="mt-1 text-[11px] text-rose-400">💡 {fup.basis}</p>}
              <div className="mt-2 flex justify-end gap-2">
                <button
                  onClick={() => setFup(null)}
                  type="button"
                  className="rounded-lg px-3 py-1.5 text-sm text-slate-500 hover:bg-white"
                >
                  건너뛰기
                </button>
                <button
                  onClick={askFollowup}
                  type="button"
                  className="rounded-lg bg-rose-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-rose-700"
                >
                  이 질문에 답변하기 →
                </button>
              </div>
            </div>
          )}

          <div className="mt-4 flex items-center justify-end gap-2">
            {phase === 'ready' && (
              <button
                onClick={startPrep}
                type="button"
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                답변 준비 (3초 후 녹화)
              </button>
            )}
            {phase === 'prep' && (
              <button disabled type="button" className="rounded-lg bg-white px-4 py-2 text-sm font-medium text-slate-400 ring-1 ring-slate-200">
                준비 중…
              </button>
            )}
            {phase === 'recording' && (
              <button
                onClick={() => void stopRecording()}
                type="button"
                className="rounded-lg bg-white px-4 py-2 text-sm font-medium text-rose-600 ring-1 ring-rose-200 hover:bg-rose-50"
              >
                ■ 답변 종료
              </button>
            )}
            {phase === 'reviewing' && !fup && !fupLoading && (
              <>
                <button
                  onClick={() => setPhase('ready')}
                  type="button"
                  className="rounded-lg bg-white px-4 py-2 text-sm font-medium text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
                >
                  다시 녹화
                </button>
                <button
                  onClick={next}
                  type="button"
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                >
                  {isLast ? 'AI 분석 요청' : '다음 문항 →'}
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

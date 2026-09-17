import { useEffect, useRef, useState } from 'react';
import { requestFollowup } from './api';
import { computeDelivery, countSyllables, PACE_MAX, PACE_MIN, type ClipEvent } from './delivery';
import { useAudioMeter, useRecorder, useSpeech, useWebcam } from './hooks';
import { saveItem } from './localVideo';
import { SOURCE_BADGE } from './styles';
import { useVision } from './vision';
import type { Followup, GeneratedQuestion, InterviewConfig, SessionItem } from './types';

interface InterviewSessionProps {
  config: InterviewConfig;
  questions: GeneratedQuestion[];
  /** 로컬 녹화를 묶는 세션 id. 저장 후 서버 면접 id 와 매칭한다. */
  localSessionId: string;
  onFinish: (items: SessionItem[]) => void;
  onExit: () => void;
}

type Phase = 'ready' | 'prep' | 'recording' | 'reviewing';
type FupStatus = 'idle' | 'loading' | 'result' | 'empty' | 'error';

const PREP_SECONDS = 3;

/** 영상 면접 진행. 문항별 웹캠 녹화 + 실시간 STT. 답변 후 옵션으로 꼬리질문을 받는다. 영상은 이 브라우저에만 저장된다. */
export function InterviewSession({ config, questions, localSessionId, onFinish, onExit }: InterviewSessionProps) {
  const { videoRef, status, stream } = useWebcam();
  const speech = useSpeech();
  const recorder = useRecorder(stream);
  const meter = useAudioMeter(stream);
  const vision = useVision(videoRef);

  const [queue, setQueue] = useState<SessionItem[]>(() =>
    questions.map((q) => ({ question: q.question, sourceType: q.sourceType, transcript: '', isFollowup: false })),
  );
  const [idx, setIdx] = useState(0);
  const [phase, setPhase] = useState<Phase>('ready');
  const [prep, setPrep] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [fup, setFup] = useState<Followup | null>(null);
  // 꼬리질문 요청 상태. idle=아직 요청 안 함, loading=요청 중, result=질문 받음(fup),
  // empty=더 물을 게 없음(needed=false), error=요청 실패(재시도 가능).
  const [fupStatus, setFupStatus] = useState<FupStatus>('idle');
  const followed = useRef<Set<number>>(new Set());
  const timerRef = useRef<number | null>(null);
  // 진행 중인 꼬리질문 요청이 어느 문항 것인지. 응답이 늦게 와도 이미 다음으로 넘어갔으면 버린다.
  const fupReqIdx = useRef<number | null>(null);

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
    recorder.start();
    meter.start();
    vision.start();
  };

  const stopRecording = async () => {
    stopTimer();
    speech.stop();
    setPhase('reviewing');

    // 녹화·음성·영상 계측 종료 → 전달·비언어 지표 계산 후 이 브라우저(IndexedDB)에만 저장. 실패해도 면접 흐름은 계속된다.
    const visionResult = vision.stop();
    const clip = await recorder.stop();
    const audio = meter.stop();
    const answer = queue[idx].transcript.trim();
    const durationSec = (clip?.durationMs ?? audio?.durationMs ?? elapsed * 1000) / 1000;
    const metrics = computeDelivery(answer, durationSec, audio);
    // 공백(오디오) + 프레임/정면/시선 이탈(비전) 을 하나의 타임라인 이벤트 목록으로 합친다.
    const events: ClipEvent[] = [
      ...(audio?.silences ?? []).map((s) => ({ kind: 'silence' as const, startMs: s.startMs, endMs: s.endMs })),
      ...(visionResult?.events ?? []),
    ].sort((a, b) => a.startMs - b.startMs);
    try {
      await saveItem({
        localSessionId,
        seq: idx + 1,
        question: current.question,
        isFollowup: current.isFollowup,
        clip,
        metrics,
        nonverbal: visionResult?.metrics ?? null,
        events,
      });
    } catch {
      /* 저장 실패(용량 초과 등)는 무시 — 분석에는 영향 없음 */
    }
    // 꼬리질문은 자동 생성하지 않는다. 사용자가 음성 인식 오류를 직접 고친 뒤 버튼으로 요청한다(requestFollowupNow).
  };

  // 이 문항에 꼬리질문을 붙일 수 있는지. followupEnabled 이고, 꼬리질문 자체가 아니며, 아직 안 붙였을 때.
  const canFollowup = config.followupEnabled && !current.isFollowup && !followed.current.has(idx);
  // '다음 문항'을 주 버튼으로 강조할지. 꼬리질문 대상이 아니거나, 요청이 끝나(더 물을 게 없음) 다음이 자연스러운 상태일 때.
  const nextIsPrimary = !canFollowup || fupStatus === 'empty' || fupStatus === 'result';

  // 사용자가 트랜스크립트를 확정한 뒤 누른다. 수정된 최신 답변으로 꼬리질문을 요청한다.
  const requestFollowupNow = async () => {
    const answer = current.transcript.trim();
    if (!canFollowup || answer.length === 0) return;
    const reqIdx = idx;
    fupReqIdx.current = reqIdx;
    setFup(null);
    setFupStatus('loading');
    try {
      const followup = await requestFollowup({
        question: current.question,
        transcript: answer,
        targetPosition: config.targetPosition,
      });
      // 응답을 기다리는 동안 다음 문항으로 넘어갔다면 무시한다.
      if (fupReqIdx.current !== reqIdx) return;
      // 더 물을 가치가 없으면 서버가 question 을 비워 보낸다(needed=false).
      if (followup.question) {
        setFup(followup);
        setFupStatus('result');
      } else {
        setFupStatus('empty');
      }
    } catch {
      if (fupReqIdx.current === reqIdx) setFupStatus('error');
    }
  };

  // 진행 중인 꼬리질문 요청·표시를 취소하고 초기 상태로 되돌린다. 문항을 넘기거나 다시 녹화할 때 호출한다.
  const cancelFollowup = () => {
    fupReqIdx.current = null;
    setFup(null);
    setFupStatus('idle');
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
    cancelFollowup();
    setIdx(idx + 1);
    setPhase('ready');
  };

  const next = () => {
    cancelFollowup();
    if (isLast) {
      onFinish(queue);
    } else {
      setIdx(idx + 1);
      setPhase('ready');
    }
  };

  const mmss = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

  // 실시간 말속도 힌트(대략치). 3초 이상 말했을 때만 노출한다.
  const liveWpm = elapsed > 0 ? Math.round((countSyllables(current.transcript) / elapsed) * 60) : 0;
  const paceOff = liveWpm > 0 && (liveWpm < PACE_MIN || liveWpm > PACE_MAX);
  const paceLabel = liveWpm === 0 ? '' : liveWpm < PACE_MIN ? '조금 빠르게' : liveWpm > PACE_MAX ? '천천히' : '좋은 속도';

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
            {phase === 'recording' && vision.warn && (
              <div className="absolute top-3 left-1/2 -translate-x-1/2 rounded-full bg-amber-500/90 px-3 py-1 text-xs font-semibold text-white shadow">
                ⚠ {vision.warn}
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
            {phase === 'recording' && meter.supported && (
              <div className="absolute inset-x-3 bottom-3 flex items-center gap-3 rounded-xl bg-slate-900/55 px-3 py-2 backdrop-blur-sm">
                <span className="text-[11px] text-slate-200">🔊</span>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/20">
                  <div
                    className="h-full rounded-full bg-emerald-400 transition-[width] duration-100"
                    style={{ width: `${Math.round(meter.level * 100)}%` }}
                  />
                </div>
                {elapsed >= 3 && paceLabel && (
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold text-white ${
                      paceOff ? 'bg-amber-500/85' : 'bg-emerald-500/85'
                    }`}
                  >
                    {liveWpm} · {paceLabel}
                  </span>
                )}
              </div>
            )}
          </div>
          <div className="flex items-center justify-between px-4 py-2 text-xs text-slate-400">
            <span>
              {recorder.supported
                ? '🎥 영상은 이 브라우저에만 저장됩니다 · 서버로 전송되지 않아요'
                : '🎥 이 브라우저는 녹화를 지원하지 않아요 · 답변 텍스트만 분석에 사용됩니다'}
            </span>
            <span>
              {vision.status === 'loading'
                ? '🧠 표정·자세 분석 준비 중…'
                : vision.status === 'ready'
                  ? '🧠 표정·자세 분석 켜짐'
                  : vision.status === 'unsupported' || vision.status === 'error'
                    ? '🧠 표정·자세 분석 미사용'
                    : ''}
            </span>
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

          {phase === 'reviewing' && canFollowup && fupStatus === 'idle' && (
            <p className="mt-3 text-xs text-slate-400">
              음성 인식이 잘못됐다면 수정 후{' '}
              <span className="font-medium text-slate-500">‘답변 확정’</span>을 눌러주세요.
            </p>
          )}

          {phase === 'reviewing' && fupStatus === 'loading' && (
            <p className="mt-3 flex items-center gap-2 text-xs text-slate-400">
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-slate-300 border-t-blue-500" />
              면접관이 추가 질문을 준비 중…
            </p>
          )}

          {phase === 'reviewing' && fupStatus === 'empty' && (
            <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-[13px] text-slate-500">
              이 답변에는 꼬리질문이 없습니다. 다음 문항으로 넘어가세요.
            </div>
          )}

          {phase === 'reviewing' && fupStatus === 'error' && (
            <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-[13px] text-amber-700">
              꼬리질문을 불러오지 못했습니다. ‘답변 확정’으로 다시 시도해 주세요.
            </div>
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
            {phase === 'reviewing' && !fup && (
              <>
                <button
                  onClick={() => {
                    cancelFollowup();
                    setPhase('ready');
                  }}
                  type="button"
                  className="rounded-lg bg-white px-4 py-2 text-sm font-medium text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
                >
                  다시 녹화
                </button>
                {canFollowup && (
                  <button
                    onClick={() => void requestFollowupNow()}
                    // 요청 전(idle)·실패(error) 에만 누를 수 있다. 한 번 누르면 로딩·결과 동안 비활성.
                    disabled={
                      current.transcript.trim().length === 0 ||
                      (fupStatus !== 'idle' && fupStatus !== 'error')
                    }
                    type="button"
                    className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                  >
                    답변 확정
                  </button>
                )}
                <button
                  onClick={next}
                  type="button"
                  className={
                    nextIsPrimary
                      ? 'rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700'
                      : 'rounded-lg bg-white px-4 py-2 text-sm font-medium text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50'
                  }
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

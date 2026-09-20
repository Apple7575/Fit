import { useEffect, useRef, useState } from 'react';
import { requestFollowup } from './api';
import { computeDelivery, countSyllables, PACE_MAX, PACE_MIN, type ClipEvent } from './delivery';
import { GuideStrip } from './GuideImage';
import { POSTURE_FIGURES } from './guideFigures';
import { useAudioMeter, useRecorder, useSpeech, useWebcam } from './hooks';
import { Icon } from './icons';
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
  // 카메라·마이크를 먼저 확인한 뒤 첫 질문으로 넘어간다
  const [checked, setChecked] = useState(false);
  const [phase, setPhase] = useState<Phase>('ready');
  // 답변을 확정했는지. 확정해야 '다음 문항'이 나온다 (문항마다 새로 시작한다)
  const [confirmed, setConfirmed] = useState(false);
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

  // 점검 → 면접으로 넘어가면 <video> 가 새로 만들어진다. 그때마다 스트림을 다시 물려준다.
  useEffect(() => {
    const el = videoRef.current;
    if (!el || !stream) return;
    el.srcObject = stream;
    void el.play().catch(() => {});
  }, [stream, checked, videoRef]);

  // 점검 화면에서만 음량 막대를 미리 돌린다 (녹화는 아직 시작하지 않는다)
  useEffect(() => {
    if (checked || !stream) return;
    meter.start();
    return () => {
      meter.stop();
    };
    // meter 는 훅이 만든 안정적인 객체라 의존성에 넣지 않는다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [checked, stream]);

  const stopTimer = () => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const startPrep = () => {
    setFup(null);
    setConfirmed(false);
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
        wave: audio?.wave ?? null,
        waveStepMs: audio?.waveStepMs ?? null,
      });
    } catch {
      /* 저장 실패(용량 초과 등)는 무시 — 분석에는 영향 없음 */
    }
    // 꼬리질문은 자동 생성하지 않는다. 사용자가 음성 인식 오류를 직접 고친 뒤 버튼으로 요청한다(requestFollowupNow).
  };

  // 이 문항에 꼬리질문을 붙일 수 있는지. followupEnabled 이고, 꼬리질문 자체가 아니며, 아직 안 붙였을 때.
  const canFollowup = config.followupEnabled && !current.isFollowup && !followed.current.has(idx);

  /**
   * 답변 확정. 여기서부터 '다음 문항'이 열린다.
   * 꼬리질문을 붙일 수 있는 문항이면 확정과 동시에 꼬리질문도 요청한다.
   */
  const confirmAnswer = () => {
    setConfirmed(true);
    if (canFollowup && current.transcript.trim().length > 0) void requestFollowupNow();
  };

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
    setConfirmed(false);
    setIdx(idx + 1);
    setPhase('ready');
  };

  const next = () => {
    cancelFollowup();
    setConfirmed(false);
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

  if (!checked) {
    return (
      <div className="mx-auto max-w-[1320px] px-5 py-6 lg:px-8">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.25fr)_minmax(320px,1fr)] lg:items-start">
          <div className="space-y-5">
          <div className="relative aspect-video overflow-hidden rounded-2xl bg-slate-900">
            <video className="h-full w-full object-cover" muted playsInline ref={videoRef} style={{ transform: 'scaleX(-1)' }} />
            <PersonGuide />
            {status === 'denied' && (
              <p className="absolute inset-0 flex items-center justify-center px-8 text-center text-sm text-slate-300">
                카메라 권한이 필요합니다. 주소창의 카메라 아이콘에서 허용해 주세요.
              </p>
            )}
            <p className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-slate-950/80 to-transparent px-4 py-3 text-[11px] text-white/70">
              점선 안에 얼굴과 어깨가 들어오게 앉아 주세요
            </p>
          </div>

          {/* 끝나고 "등이 굽었습니다"를 듣는 것보다, 시작 전에 보는 편이 낫다 */}
          <GuideStrip figures={POSTURE_FIGURES} title="이렇게 앉으면 됩니다" />
          </div>

          <aside>
            <button className="text-sm text-slate-400 transition hover:text-slate-600" onClick={onExit} type="button">
              ← 설정으로
            </button>
            <h1 className="mt-2 text-xl font-extrabold tracking-tight text-slate-950">시작 전에 확인할게요</h1>
            <p className="mt-1 text-[13px] text-slate-500">평소 말하듯 한 문장을 소리 내 보세요.</p>

            <ul className="mt-4 space-y-2">
              <CheckRow
                label="카메라"
                note={status === 'live' ? '연결됨' : status === 'denied' ? '권한이 거부됐어요' : '연결하는 중…'}
                ok={status === 'live'}
              />
              <CheckRow
                label="마이크"
                note={
                  !meter.supported
                    ? '이 브라우저는 음량 측정을 지원하지 않아요'
                    : meter.level > 0.02
                      ? '소리가 잘 들려요'
                      : '말해 보면 막대가 움직여요'
                }
                ok={meter.supported && meter.level > 0.02}
              >
                <span aria-hidden="true" className="ml-2 h-1.5 w-16 overflow-hidden rounded-full bg-slate-200">
                  <span
                    className="block h-full rounded-full bg-emerald-500 transition-[width] duration-100"
                    style={{ width: `${Math.round(Math.min(1, meter.level * 3) * 100)}%` }}
                  />
                </span>
              </CheckRow>
              <CheckRow
                label="음성 인식"
                note={speech.supported ? '답변이 자동으로 받아써집니다' : '미지원 — 직접 입력해 주세요'}
                ok={speech.supported}
              />
              <CheckRow
                label="표정·자세 분석"
                note={
                  vision.status === 'loading'
                    ? '준비 중…'
                    : vision.status === 'unsupported' || vision.status === 'error'
                      ? '미사용 — 답변 내용만 분석해요'
                      : '이 브라우저 안에서만 처리됩니다'
                }
                ok={vision.status === 'ready' || vision.status === 'idle'}
              />
            </ul>

            {/*
              "내 얼굴을 찍는데 왜" 라는 망설임을 없애는 문장이다. 11px 회색 각주로 두면 아무도
              읽지 않으므로, 시작 버튼 위에 제대로 적는다.
            */}
            <div className="mt-5 rounded-2xl border border-emerald-200/70 bg-emerald-50/50 p-4">
              <p className="flex items-center gap-2 text-[14px] font-bold text-emerald-900">
                {/* className 은 기본 크기를 덮어쓴다. 크기를 함께 적지 않으면 아이콘이 칸을 다 먹는다 */}
                <Icon className="size-4 shrink-0 text-emerald-600" name="check" />
                영상은 이 브라우저 밖으로 나가지 않습니다
              </p>
              <p className="mt-1.5 text-[12px] leading-5 break-keep text-emerald-800/80">
                녹화도 표정·자세 분석도 이 기기 안에서만 돌아갑니다. 서버로 보내는 것은 받아쓴 답변
                글자뿐입니다.
              </p>
            </div>

            <button
              className="mt-4 w-full rounded-full bg-slate-900 px-6 py-3 text-sm font-bold text-white transition hover:bg-slate-950 disabled:opacity-40"
              disabled={status !== 'live'}
              onClick={() => setChecked(true)}
              type="button"
            >
              {queue.length}문항 면접 시작
            </button>
          </aside>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1320px] px-5 py-4 lg:px-8">
      <div className="mb-3 flex items-center justify-between gap-4">
        <button className="text-sm text-slate-400 transition hover:text-slate-600" onClick={onExit} type="button">
          ← 나가기
        </button>
        <ol aria-label="문항 진행" className="flex items-center gap-1.5">
          {queue.map((item, i) => (
            <li
              className={`h-1.5 rounded-full transition-all ${
                i === idx
                  ? item.isFollowup
                    ? 'w-8 bg-rose-500'
                    : 'w-8 bg-slate-900'
                  : i < idx
                    ? 'w-4 bg-slate-400'
                    : 'w-4 bg-slate-200'
              }`}
              key={i}
            />
          ))}
        </ol>
        <span className="text-sm font-semibold tabular-nums text-slate-500">
          {idx + 1} / {queue.length}
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(360px,0.9fr)] lg:items-start">
        {/* 왼쪽: 내 화면 (영상 카드는 테두리 없이 까맣게) */}
        <div className="relative aspect-video overflow-hidden rounded-2xl bg-slate-900">
          <video className="h-full w-full object-cover" muted playsInline ref={videoRef} style={{ transform: 'scaleX(-1)' }} />
          {status === 'denied' && (
            <p className="absolute inset-0 flex items-center justify-center px-8 text-center text-sm text-slate-300">
              카메라 권한이 필요합니다. 주소창의 카메라 아이콘에서 허용해 주세요.
            </p>
          )}
          {phase === 'prep' && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950/70">
              <span className="text-7xl font-extrabold tabular-nums text-white">{prep}</span>
              <span className="mt-2 text-sm text-slate-300">잠시 후 녹화가 시작됩니다</span>
            </div>
          )}
          {phase === 'recording' && (
            <span className="absolute left-3 top-3 flex items-center gap-1.5 rounded-full bg-rose-600 px-2.5 py-1 text-xs font-bold text-white">
              <span className="size-2 animate-pulse rounded-full bg-white" /> REC {mmss(elapsed)}
            </span>
          )}
          {phase === 'recording' && (
            <div className="absolute inset-x-3 bottom-3 flex items-center gap-2">
              {meter.supported && (
                <span aria-hidden="true" className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/20">
                  <span
                    className="block h-full rounded-full bg-emerald-400 transition-[width] duration-100"
                    style={{ width: `${Math.round(meter.level * 100)}%` }}
                  />
                </span>
              )}
              {vision.warn && (
                <span className="rounded-full bg-amber-500/90 px-2.5 py-1 text-[11px] font-semibold text-white">
                  {vision.warn}
                </span>
              )}
              {elapsed >= 3 && paceOff && paceLabel && (
                <span className="rounded-full bg-amber-500/90 px-2.5 py-1 text-[11px] font-semibold text-white">
                  {paceLabel}
                </span>
              )}
            </div>
          )}
        </div>

        {/* 오른쪽: 질문과 답변 (흰 카드) */}
        <div className="flex flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="flex flex-wrap items-center gap-2 text-[11px] font-bold">
            <span className={`rounded-full px-2 py-0.5 ring-1 ${badge.className}`}>{badge.label}</span>
            {config.targetCompany && <span className="text-slate-400">{config.targetCompany}</span>}
            <span className="ml-auto text-slate-300">Q{idx + 1}</span>
          </p>
          <p className="mt-3 text-[19px] font-extrabold leading-8 text-slate-950 break-keep">{current.question}</p>
          {current.isFollowup && (
            <p className="mt-1.5 text-xs text-rose-500">직전 답변을 듣고 면접관이 드리는 추가 질문입니다.</p>
          )}

          {/* 답변은 한 자리에서만 보여준다 (녹화 중에는 받아쓰기, 끝나면 수정) */}
          <div className="mt-4 flex-1">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-[11px] font-bold text-slate-400">
                {phase === 'recording' ? '실시간 받아쓰기' : '내 답변'}
              </span>
              {phase === 'reviewing' && <span className="text-[11px] text-slate-400">잘못 들린 부분은 고칠 수 있어요</span>}
            </div>
            {phase === 'recording' ? (
              <p className="mt-1.5 max-h-56 min-h-32 overflow-y-auto rounded-xl bg-slate-50 p-3 text-[14px] leading-6 text-slate-700 break-keep">
                {current.transcript || <span className="text-slate-400">말씀하시면 여기에 바로 받아써집니다…</span>}
              </p>
            ) : (
              <textarea
                className="mt-1.5 h-32 w-full resize-none rounded-xl border border-slate-200 bg-slate-50 p-3 text-[14px] leading-6 text-slate-700 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                onChange={(e) => setTranscript(e.target.value)}
                placeholder={phase === 'ready' ? '답변을 시작하면 여기에 받아써집니다.' : ''}
                value={current.transcript}
              />
            )}
          </div>

          {phase === 'reviewing' && fupStatus === 'loading' && (
            <p className="mt-2 flex items-center gap-2 text-xs text-slate-400">
              <span className="size-3 animate-spin rounded-full border-2 border-slate-300 border-t-blue-500" />
              면접관이 추가 질문을 준비 중…
            </p>
          )}
          {phase === 'reviewing' && fupStatus === 'empty' && (
            <p className="mt-2 rounded-xl bg-slate-50 p-3 text-[13px] text-slate-500">
              이 답변에는 꼬리질문이 없습니다. 다음 문항으로 넘어가세요.
            </p>
          )}
          {phase === 'reviewing' && fupStatus === 'error' && (
            <p className="mt-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-[13px] text-amber-700">
              추가 질문을 불러오지 못했습니다. 그대로 다음 문항으로 넘어가셔도 됩니다.
            </p>
          )}
          {phase === 'reviewing' && fup && (
            <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50/70 p-3">
              <p className="text-[11px] font-bold text-rose-600">면접관의 추가 질문</p>
              <p className="mt-1 text-[14px] font-semibold leading-6 text-slate-800 break-keep">{fup.question}</p>
              {fup.basis && <p className="mt-1 text-[11px] text-rose-400">{fup.basis}</p>}
              <div className="mt-2 flex justify-end gap-2">
                <button
                  className="rounded-lg px-3 py-1.5 text-sm text-slate-500 hover:bg-white"
                  onClick={() => setFup(null)}
                  type="button"
                >
                  건너뛰기
                </button>
                <button
                  className="rounded-lg bg-rose-600 px-4 py-1.5 text-sm font-semibold text-white hover:bg-rose-700"
                  onClick={askFollowup}
                  type="button"
                >
                  이 질문에 답변하기
                </button>
              </div>
            </div>
          )}

          <div className="mt-4 flex flex-wrap items-center justify-end gap-2">
            {phase === 'ready' && (
              <button
                className="flex items-center gap-2 rounded-full bg-slate-900 px-6 py-2.5 text-sm font-bold text-white transition hover:bg-slate-950"
                onClick={startPrep}
                type="button"
              >
                <Icon name="mic" />
                답변 시작 (3초 후 녹화)
              </button>
            )}
            {phase === 'prep' && <span className="text-sm font-semibold text-slate-400">{prep}초 뒤 시작합니다…</span>}
            {phase === 'recording' && (
              <button
                className="flex items-center gap-2 rounded-full bg-rose-600 px-6 py-2.5 text-sm font-bold text-white transition hover:bg-rose-700"
                onClick={() => void stopRecording()}
                type="button"
              >
                <Icon name="stop" />
                답변 종료
              </button>
            )}
            {phase === 'reviewing' && !fup && (
              <>
                <button
                  className="flex items-center gap-2 rounded-lg bg-white px-4 py-2 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
                  onClick={() => {
                    cancelFollowup();
                    setConfirmed(false);
                    setPhase('ready');
                  }}
                  type="button"
                >
                  <Icon name="redo" />
                  다시 녹화
                </button>
                {/* 답변을 확정해야 다음으로 넘어갈 수 있다. 확정 전에 문항이 넘어가면 부자연스럽다 */}
                {!confirmed ? (
                  <button
                    className="flex items-center gap-2 rounded-lg bg-slate-900 px-5 py-2 text-sm font-semibold text-white transition hover:bg-slate-950 disabled:cursor-not-allowed disabled:opacity-40"
                    disabled={fupStatus === 'loading'}
                    onClick={confirmAnswer}
                    type="button"
                  >
                    <Icon name="check" />
                    답변 확정
                  </button>
                ) : (
                  <button
                    className="flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold text-white transition hover:bg-blue-700"
                    onClick={next}
                    type="button"
                  >
                    <Icon name="next" />
                    {isLast ? 'AI 분석 요청' : '다음 문항'}
                  </button>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/** 카메라 안에서 앉을 위치를 알려주는 사람 실루엣 (머리 + 어깨) */
function PersonGuide() {
  return (
    <svg
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 h-full w-full"
      fill="none"
      preserveAspectRatio="xMidYMid meet"
      viewBox="0 0 160 90"
    >
      <circle cx="80" cy="34" r="15" stroke="rgba(255,255,255,0.35)" strokeDasharray="4 4" strokeWidth="1" />
      <path
        d="M52 90c0-16 12.5-27 28-27s28 11 28 27"
        stroke="rgba(255,255,255,0.35)"
        strokeDasharray="4 4"
        strokeWidth="1"
      />
    </svg>
  );
}

/** 장비 점검 한 줄 */
function CheckRow({
  label,
  ok,
  note,
  children,
}: {
  label: string;
  ok: boolean;
  note: string;
  children?: React.ReactNode;
}) {
  return (
    <li className="flex items-center gap-2.5 rounded-xl border border-slate-200 bg-white px-3 py-2.5">
      <span
        aria-hidden="true"
        className={`flex size-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white ${
          ok ? 'bg-emerald-500' : 'bg-slate-300'
        }`}
      >
        {ok ? '✓' : '…'}
      </span>
      <span className="text-[13px] font-semibold text-slate-800">{label}</span>
      <span className="min-w-0 flex-1 truncate text-[11px] text-slate-500">{note}</span>
      {children}
    </li>
  );
}

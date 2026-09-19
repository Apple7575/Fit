import { useCallback, useEffect, useRef, useState } from 'react';
import type { AudioStats } from './delivery';

export type WebcamStatus = 'idle' | 'live' | 'denied';

/**
 * 웹캠 프리뷰 + 공유 스트림. 스트림 하나를 프리뷰·녹화·계측이 함께 쓴다.
 * 스트림은 서버로 보내지 않으며 언마운트 시 트랙을 끈다.
 */
export function useWebcam() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [status, setStatus] = useState<WebcamStatus>('idle');
  const [stream, setStream] = useState<MediaStream | null>(null);

  useEffect(() => {
    let local: MediaStream | null = null;
    let cancelled = false;
    navigator.mediaDevices
      // 셀프리뷰·랜드마크 검출엔 저해상도로 충분하다. 녹화 용량을 줄이려 해상도·프레임을 고정한다.
      .getUserMedia({ video: { width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 24 } }, audio: true })
      .then((s) => {
        local = s;
        if (cancelled) {
          s.getTracks().forEach((t) => t.stop());
          return;
        }
        if (videoRef.current) {
          videoRef.current.srcObject = s;
          void videoRef.current.play();
        }
        setStream(s);
        setStatus('live');
      })
      .catch(() => {
        if (!cancelled) setStatus('denied');
      });
    return () => {
      cancelled = true;
      if (local) local.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return { videoRef, status, stream };
}

export interface RecordedClip {
  blob: Blob;
  mime: string;
  durationMs: number;
}

// 브라우저마다 지원 코덱이 달라 되는 것을 우선순위대로 고른다(webm 우선, Safari 는 mp4).
const REC_MIME_CANDIDATES = [
  'video/webm;codecs=vp9,opus',
  'video/webm;codecs=vp8,opus',
  'video/webm',
  'video/mp4',
];

function pickRecMime(): string | null {
  if (typeof MediaRecorder === 'undefined') return null;
  for (const m of REC_MIME_CANDIDATES) {
    if (MediaRecorder.isTypeSupported(m)) return m;
  }
  return null;
}

/**
 * 공유 스트림을 문항별로 녹화한다. stop() 이 합쳐진 Blob 을 돌려주고 저장은 호출측이 로컬에 한다.
 * MediaRecorder 미지원이면 supported=false → 녹화만 비활성(음성·분석은 계속 동작).
 */
export function useRecorder(stream: MediaStream | null) {
  const recRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef(0);
  const [supported] = useState(() => pickRecMime() !== null);

  const start = useCallback(() => {
    if (!stream) return;
    const mime = pickRecMime();
    if (!mime) return;
    let rec: MediaRecorder;
    try {
      // 셀프리뷰 용도라 저비트레이트로 충분하다(용량 절약). 오디오도 명시적으로 낮춘다.
      rec = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 700_000, audioBitsPerSecond: 64_000 });
    } catch {
      return;
    }
    chunksRef.current = [];
    rec.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    recRef.current = rec;
    startedAtRef.current = Date.now();
    rec.start();
  }, [stream]);

  const stop = useCallback((): Promise<RecordedClip | null> => {
    const rec = recRef.current;
    recRef.current = null;
    if (!rec || rec.state === 'inactive') return Promise.resolve(null);
    return new Promise((resolve) => {
      rec.onstop = () => {
        const chunks = chunksRef.current;
        chunksRef.current = [];
        if (chunks.length === 0) {
          resolve(null);
          return;
        }
        const mime = rec.mimeType || 'video/webm';
        resolve({ blob: new Blob(chunks, { type: mime }), mime, durationMs: Date.now() - startedAtRef.current });
      };
      try {
        rec.stop();
      } catch {
        resolve(null);
      }
    });
  }, []);

  useEffect(
    () => () => {
      const rec = recRef.current;
      if (rec && rec.state !== 'inactive') {
        try {
          rec.stop();
        } catch {
          /* noop */
        }
      }
    },
    [],
  );

  return { supported, start, stop };
}

// 무음 판정 임계(float RMS). 마이크 게인마다 달라 절대 음량은 참고만 하고 침묵 구분에만 쓴다.
const SILENCE_RMS = 0.015;
const SAMPLE_MS = 50;
// 타임라인 마커로 남길 최소 공백 길이. 너무 짧은 숨 고르기는 표시하지 않는다.
const SILENCE_EVENT_MS = 2000;

function audioCtor(): typeof AudioContext | null {
  const w = window as unknown as { AudioContext?: typeof AudioContext; webkitAudioContext?: typeof AudioContext };
  return w.AudioContext ?? w.webkitAudioContext ?? null;
}

/** 파형은 5Hz(200ms) 로 줄여 저장한다. 1분 답변이면 300칸이라 IndexedDB 에 부담이 없다 */
const WAVE_STEP_MS = 200;

function summarizeWave(samples: number[]): number[] {
  const per = Math.max(1, Math.round(WAVE_STEP_MS / SAMPLE_MS));
  const out: number[] = [];
  for (let i = 0; i < samples.length; i += per) {
    const chunk = samples.slice(i, i + per);
    const peak = chunk.reduce((a, x) => Math.max(a, x), 0);
    // 화면에 그릴 값이라 0~1 로 맞춘다 (rms 는 보통 0.3 이하)
    out.push(Math.round(Math.min(1, peak * 4) * 100) / 100);
  }
  return out;
}

function summarizeAudio(samples: number[], durationMs: number): AudioStats {
  const speech = samples.filter((r) => r >= SILENCE_RMS);
  const silenceRatio = samples.length ? (samples.length - speech.length) / samples.length : 1;
  let longestSilence = 0;
  let run = 0;
  let runStart = 0;
  let startDelay = 0;
  let seenSpeech = false;
  const silences: Array<{ startMs: number; endMs: number }> = [];
  const flushSilence = (endIdx: number) => {
    const startMs = runStart * SAMPLE_MS;
    const endMs = endIdx * SAMPLE_MS;
    if (endMs - startMs >= SILENCE_EVENT_MS) silences.push({ startMs, endMs });
  };
  for (let i = 0; i < samples.length; i++) {
    if (samples[i] < SILENCE_RMS) {
      if (run === 0) runStart = i;
      run += SAMPLE_MS;
      if (run > longestSilence) longestSilence = run;
      if (!seenSpeech) startDelay += SAMPLE_MS;
    } else {
      if (run > 0) flushSilence(i);
      run = 0;
      seenSpeech = true;
    }
  }
  if (run > 0) flushSilence(samples.length);
  const mean = speech.length ? speech.reduce((a, r) => a + r, 0) / speech.length : 0;
  const variance = speech.length ? speech.reduce((a, r) => a + (r - mean) ** 2, 0) / speech.length : 0;
  const volumeCV = mean > 0 ? Math.sqrt(variance) / mean : 0;
  return {
    wave: summarizeWave(samples),
    waveStepMs: WAVE_STEP_MS,
    durationMs,
    silenceRatio,
    longestSilenceMs: longestSilence,
    startDelayMs: startDelay,
    volumeMean: mean,
    volumeCV,
    hadSignal: speech.length > 0,
    silences,
  };
}

/**
 * 공유 스트림의 음량을 RMS 로 샘플링한다. 실시간 표시용 level(0~1)과, stop() 에서 침묵·음량 통계를 돌려준다.
 * Web Audio 미지원이면 supported=false → 음성 지표는 스킵(말속도·군더더기 등 텍스트 지표는 유지).
 */
export function useAudioMeter(stream: MediaStream | null) {
  const ctxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const bufRef = useRef<Float32Array<ArrayBuffer> | null>(null);
  const timerRef = useRef<number | null>(null);
  const samplesRef = useRef<number[]>([]);
  const startedAtRef = useRef(0);
  const [level, setLevel] = useState(0);
  const [supported] = useState(() => audioCtor() !== null);

  const start = useCallback(() => {
    if (!stream) return;
    try {
      if (!ctxRef.current) {
        const Ctor = audioCtor();
        if (!Ctor) return;
        const ctx = new Ctor();
        const source = ctx.createMediaStreamSource(stream);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 1024;
        source.connect(analyser);
        ctxRef.current = ctx;
        analyserRef.current = analyser;
        bufRef.current = new Float32Array(new ArrayBuffer(analyser.fftSize * 4));
      }
      void ctxRef.current.resume();
    } catch {
      return;
    }
    samplesRef.current = [];
    startedAtRef.current = Date.now();
    timerRef.current = window.setInterval(() => {
      const analyser = analyserRef.current;
      const buf = bufRef.current;
      if (!analyser || !buf) return;
      analyser.getFloatTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
      const rms = Math.sqrt(sum / buf.length);
      samplesRef.current.push(rms);
      setLevel(Math.min(1, rms * 6));
    }, SAMPLE_MS);
  }, [stream]);

  const stop = useCallback((): AudioStats | null => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setLevel(0);
    const samples = samplesRef.current;
    samplesRef.current = [];
    if (samples.length === 0) return null;
    return summarizeAudio(samples, Date.now() - startedAtRef.current);
  }, []);

  useEffect(
    () => () => {
      if (timerRef.current !== null) window.clearInterval(timerRef.current);
      if (ctxRef.current) {
        try {
          void ctxRef.current.close();
        } catch {
          /* noop */
        }
        ctxRef.current = null;
      }
    },
    [],
  );

  return { supported, level, start, stop };
}

// Web Speech API 는 표준 DOM 타입에 없어(vendor) 최소 타입만 선언한다.
interface RecognitionAlternative {
  transcript: string;
}
interface RecognitionResult {
  isFinal: boolean;
  0: RecognitionAlternative;
}
interface RecognitionResultList {
  length: number;
  [index: number]: RecognitionResult;
}
interface RecognitionEvent {
  resultIndex: number;
  results: RecognitionResultList;
}
interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start(): void;
  stop(): void;
  onresult: ((event: RecognitionEvent) => void) | null;
  onend: (() => void) | null;
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getRecognitionCtor(): SpeechRecognitionCtor | null {
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

/**
 * 브라우저 음성 인식(STT). Chrome 계열만 지원. 무음/장시간에 자동 종료되므로 onend 에서 재시작한다.
 * 미지원 브라우저면 supported=false → 화면이 수동 입력으로 폴백한다.
 */
export function useSpeech() {
  const ctorRef = useRef<SpeechRecognitionCtor | null>(getRecognitionCtor());
  const recRef = useRef<SpeechRecognitionLike | null>(null);
  const activeRef = useRef(false);
  const [supported] = useState(() => getRecognitionCtor() !== null);

  const start = useCallback((onText: (text: string) => void) => {
    const Ctor = ctorRef.current;
    if (!Ctor) return;
    const rec = new Ctor();
    rec.lang = 'ko-KR';
    rec.continuous = true;
    rec.interimResults = true;
    let finalText = '';
    rec.onresult = (event) => {
      let interim = '';
      const results = event.results;
      for (let i = event.resultIndex; i < results.length; i++) {
        const segment = results[i];
        if (segment.isFinal) finalText += segment[0].transcript;
        else interim += segment[0].transcript;
      }
      onText(finalText + interim);
    };
    rec.onend = () => {
      if (activeRef.current) {
        try {
          rec.start();
        } catch {
          /* 이미 시작됨 등은 무시 */
        }
      }
    };
    recRef.current = rec;
    activeRef.current = true;
    try {
      rec.start();
    } catch {
      /* noop */
    }
  }, []);

  const stop = useCallback(() => {
    activeRef.current = false;
    const rec = recRef.current;
    recRef.current = null;
    if (rec) {
      try {
        rec.stop();
      } catch {
        /* noop */
      }
    }
  }, []);

  useEffect(() => () => stop(), [stop]);

  return { supported, start, stop };
}

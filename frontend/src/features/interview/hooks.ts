import { useCallback, useEffect, useRef, useState } from 'react';

export type WebcamStatus = 'idle' | 'live' | 'denied';

/** 웹캠 프리뷰. 스트림은 저장하지 않고 화면 표시에만 쓴다. 언마운트 시 트랙을 끈다. */
export function useWebcam() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [status, setStatus] = useState<WebcamStatus>('idle');

  useEffect(() => {
    let stream: MediaStream | null = null;
    let cancelled = false;
    navigator.mediaDevices
      .getUserMedia({ video: { width: 640 }, audio: true })
      .then((s) => {
        stream = s;
        if (cancelled) {
          s.getTracks().forEach((t) => t.stop());
          return;
        }
        if (videoRef.current) {
          videoRef.current.srcObject = s;
          void videoRef.current.play();
        }
        setStatus('live');
      })
      .catch(() => {
        if (!cancelled) setStatus('denied');
      });
    return () => {
      cancelled = true;
      if (stream) stream.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return { videoRef, status };
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

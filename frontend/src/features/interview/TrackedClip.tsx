import { useEffect, useRef, useState, type SyntheticEvent } from 'react';
import { FRONTAL_DEG, ROLL_WARN, type VisionSample } from './vision';
import { T, TONE } from './reportTokens';

/** 눈동자가 이만큼 벗어나면 렌즈를 안 본 것으로 본다 (vision.summarize 와 같은 값) */
const GAZE_OFF = 0.15;

/** 재생 위치에 가장 가까운 샘플. 0.1초 간격이라 앞에서부터 훑어도 충분히 빠르다 */
function sampleAt(samples: VisionSample[], ms: number): VisionSample | null {
  if (samples.length === 0) return null;
  let best = samples[0];
  for (const s of samples) {
    if (s.t <= ms) best = s;
    else break;
  }
  // 한참 떨어진 값은 그 순간의 것이 아니다 (얼굴을 놓친 구간)
  return Math.abs(best.t - ms) <= 600 ? best : null;
}

/**
 * 그 순간 무엇이 어긋났는지 한 줄로. 없으면 null.
 * 화면에 여러 개를 띄우면 읽지 못하므로 가장 큰 것 하나만 말한다.
 */
function issueOf(s: VisionSample): string | null {
  if (!s.frontal) return '고개가 정면에서 벗어났어요';
  if (s.roll != null && Math.abs(s.roll) > ROLL_WARN) return '고개가 기울었어요';
  if (s.gaze > GAZE_OFF) return '시선이 렌즈를 비껴갔어요';
  return null;
}

/**
 * 녹화 영상 위에 그때의 추적을 겹쳐 그린다.
 *
 * <p>"시선이 자주 흔들렸습니다"라는 문장보다, 그 순간의 내 얼굴 위에 네모와 각도가 얹힌
 * 화면이 훨씬 빨리 납득된다. 면접을 보는 동안에는 이런 걸 띄우면 집중이 깨지므로
 * 끝난 뒤 리포트에서만 보여준다.
 *
 * <p>추적값이 없는 옛 기록에서는 겹쳐 그리기 없이 영상만 나온다.
 */
export function TrackedClip({
  src,
  samples,
  onLoadedMetadata,
  videoRef,
  onBroken,
}: {
  src: string;
  samples: VisionSample[] | null;
  onLoadedMetadata?: (e: SyntheticEvent<HTMLVideoElement>) => void;
  /** 타임라인 칩이 이 영상을 특정 시각으로 옮길 수 있게 바깥과 공유한다 */
  videoRef: React.RefObject<HTMLVideoElement | null>;
  /** 이 파일로는 재생할 수 없을 때. 바깥에서 대신 안내를 띄운다 */
  onBroken?: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [now, setNow] = useState<VisionSample | null>(null);
  const [on, setOn] = useState(true);

  /*
   * 재생 중에는 매 프레임 그린다. timeupdate 는 초당 네 번쯤이라 네모가 끊겨 보인다.
   * 멈춰 있을 때도 한 번은 그려야 정지 화면에 네모가 남는다.
   */
  useEffect(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !samples || samples.length === 0 || !on) {
      setNow(null);
      canvas?.getContext('2d')?.clearRect(0, 0, canvas.width, canvas.height);
      return;
    }

    let frame = 0;
    const draw = () => {
      const ctx = canvas.getContext('2d');
      if (ctx) {
        const w = (canvas.width = canvas.clientWidth);
        const h = (canvas.height = canvas.clientHeight);
        ctx.clearRect(0, 0, w, h);
        const s = sampleAt(samples, video.currentTime * 1000);
        setNow(s);
        if (s) paint(ctx, s, w, h);
      }
      frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [samples, on, videoRef]);

  const has = samples != null && samples.length > 0;
  const issue = now ? issueOf(now) : null;

  return (
    <div>
      <div className="relative overflow-hidden rounded-xl bg-slate-900">
        {/*
          녹화가 몇 백 바이트짜리로 끝나는 일이 있다(머리말만 쓰이고 프레임이 한 장도 안 들어간
          경우). 그대로 두면 까만 상자에 0:00 만 뜬 채 아무 설명이 없어 고장으로 읽힌다.
        */}
        <video
          className="w-full"
          controls
          onError={onBroken}
          onLoadedMetadata={onLoadedMetadata}
          playsInline
          ref={videoRef}
          src={src}
        />
        {/* 영상은 거울처럼 찍히지 않고 그대로 저장되므로 좌표를 뒤집지 않는다 */}
        <canvas
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 size-full"
          ref={canvasRef}
        />
        {issue && (
          <p className="pointer-events-none absolute inset-x-0 top-0 bg-gradient-to-b from-black/70 to-transparent px-3 py-2 text-[12px] font-bold text-white">
            {issue}
          </p>
        )}
      </div>

      {has ? (
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <Readout
            label="정면에서"
            ok={now ? now.frontal : true}
            value={now?.yaw != null ? `${Math.abs(now.yaw)}°` : '—'}
          />
          <Readout
            label="고개 기울기"
            ok={now?.roll == null || Math.abs(now.roll) <= ROLL_WARN}
            value={now?.roll != null ? `${Math.abs(now.roll)}°` : '—'}
          />
          <Readout
            label="시선"
            ok={now ? now.gaze <= GAZE_OFF : true}
            value={now ? (now.gaze <= GAZE_OFF ? '렌즈' : '비껴감') : '—'}
          />
          <button
            className="ml-auto text-[12px] font-semibold text-slate-400 transition hover:text-slate-700"
            onClick={() => setOn((v) => !v)}
            type="button"
          >
            {on ? '겹쳐 보기 끄기' : '겹쳐 보기'}
          </button>
        </div>
      ) : (
        <p className={`mt-2 ${T.caption}`}>
          이 기록에는 추적값이 없어요. 다음 면접부터 영상 위에서 같이 볼 수 있습니다.
        </p>
      )}
      {has && (
        <p className={`mt-1 ${T.caption}`}>
          재생하면 그 순간의 값이 함께 움직입니다. 어긋난 순간에만 화면에 네모가 뜹니다
          (정면에서 {FRONTAL_DEG}도 안쪽이면 적정).
        </p>
      )}
    </div>
  );
}

/** 지금 값 한 칸. 기준을 벗어난 값만 빨갛게 */
function Readout({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  const tone = ok ? TONE.good : TONE.warn;
  return (
    <span className="flex items-center gap-1.5">
      <span aria-hidden="true" className={`inline-block size-1.5 rounded-full ${tone.dot}`} />
      <span className={T.caption}>{label}</span>
      <span className={`text-[13px] font-bold tabular-nums ${tone.text}`}>{value}</span>
    </span>
  );
}

/**
 * 어긋난 순간에만 그린다. 좌표는 0~1 비율이라 화면 크기에 맞춰 늘린다.
 *
 * <p>잘하고 있을 때까지 네모를 띄우면 내 얼굴 위에 상자가 내내 얹혀 있어 정작 볼 것을 가린다.
 * 겹쳐 그리기의 일은 "이때 이랬다"를 짚는 것이므로, 문제가 있는 순간에만 나타난다.
 */
function paint(ctx: CanvasRenderingContext2D, s: VisionSample, w: number, h: number) {
  if (!issueOf(s)) return;

  ctx.lineWidth = 2;
  ctx.strokeStyle = 'rgba(239,68,68,0.95)';
  ctx.strokeRect(s.x * w, s.y * h, s.w * w, s.h * h);

  // 어깨선 — 기울었는지 눈으로 보인다
  if (s.sl && s.sr) {
    ctx.strokeStyle = 'rgba(255,255,255,0.7)';
    ctx.beginPath();
    ctx.moveTo(s.sl[0] * w, s.sl[1] * h);
    ctx.lineTo(s.sr[0] * w, s.sr[1] * h);
    ctx.stroke();
  }
}

import { useEffect, useRef } from 'react';
import { T } from './reportTokens';
import type { VisionSample } from './vision';

/** 두 장면이 이만큼은 떨어져 있어야 "다른 순간"이라고 할 수 있다 */
const MIN_GAP_MS = 1500;

/** 표정이 가장 밝았던 때와 가장 굳었던 때 */
function pickMoments(samples: VisionSample[]): { high: VisionSample; low: VisionSample } | null {
  const withSmile = samples.filter((s) => s.smile != null);
  if (withSmile.length < 10) return null;

  let high = withSmile[0];
  let low = withSmile[0];
  for (const s of withSmile) {
    if ((s.smile as number) > (high.smile as number)) high = s;
    if ((s.smile as number) < (low.smile as number)) low = s;
  }
  // 같은 순간이면 비교가 되지 않는다
  return Math.abs(high.t - low.t) >= MIN_GAP_MS ? { high, low } : null;
}

/** 그 시각에서 멈춘 한 장면 */
function Still({ url, atMs, caption }: { url: string; atMs: number; caption: string }) {
  const ref = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = ref.current;
    if (!video) return;
    const seek = () => {
      // webm 은 길이를 모르면 탐색이 실패한다. 한 번 끝까지 갔다 오면 길이가 잡힌다
      if (!Number.isFinite(video.duration)) {
        video.currentTime = 1e101;
        window.setTimeout(() => {
          video.currentTime = atMs / 1000;
        }, 150);
        return;
      }
      video.currentTime = atMs / 1000;
    };
    if (video.readyState >= 1) seek();
    else video.addEventListener('loadedmetadata', seek, { once: true });
    return () => video.removeEventListener('loadedmetadata', seek);
  }, [url, atMs]);

  return (
    <figure>
      <video className="w-full rounded-xl bg-slate-900" muted playsInline preload="metadata" ref={ref} src={url} />
      <figcaption className={`mt-1.5 text-center ${T.caption}`}>
        {caption} · {(atMs / 1000).toFixed(1)}초
      </figcaption>
    </figure>
  );
}

/**
 * 표정 근거. 가장 밝았던 순간과 가장 굳었던 순간을 나란히 세운다.
 *
 * <p>"표정이 내내 굳어 있었어요"라고만 하면 "나는 잘한 것 같은데?" 라는 생각이 든다.
 * 답변 중 가장 밝았던 얼굴과 가장 굳었던 얼굴이 나란히 놓였을 때 둘이 똑같아 보이면,
 * 설명보다 그 두 장면이 훨씬 빨리 납득시킨다.
 */
export function FaceCompare({
  url,
  samples,
  flat,
}: {
  url: string | undefined;
  samples: VisionSample[] | null;
  /** 표정이 거의 움직이지 않았다고 판정됐는지. 문구가 달라진다 */
  flat: boolean;
}) {
  const moments = samples ? pickMoments(samples) : null;

  if (!url || !moments) {
    return (
      <p className={T.caption}>
        이 답변에는 표정을 되돌려 볼 기록이 없어요. 다음 면접부터 두 장면을 나란히 볼 수 있습니다.
      </p>
    );
  }

  return (
    <div>
      <p className={T.label}>{flat ? '가장 밝았던 때와 가장 굳었던 때' : '표정이 가장 달랐던 두 순간'}</p>
      <div className="mt-2 grid grid-cols-2 gap-3">
        <Still atMs={moments.high.t} caption="가장 밝았던 때" url={url} />
        <Still atMs={moments.low.t} caption="가장 굳었던 때" url={url} />
      </div>
      <p className={`mt-2 break-keep ${T.body}`}>
        {flat
          ? '두 장면이 비슷해 보인다면, 답변 내내 같은 표정이었다는 뜻이에요.'
          : '이만큼은 달라졌어요. 듣는 쪽에서는 이 차이가 잘 보입니다.'}
      </p>
    </div>
  );
}

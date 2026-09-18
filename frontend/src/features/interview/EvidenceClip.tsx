import { useEffect, useRef, useState } from 'react';
import { EVENT_META, type ClipEvent } from './delivery';

interface EvidenceClipProps {
  url: string;
  events: ClipEvent[];
}

/** 구간 앞뒤로 조금 더 보여줘야 무슨 일이 있었는지 알 수 있다 */
const PAD_MS = 700;

/**
 * 근거 구간 재생기. 저장된 녹화에서 그 구간만 반복 재생하고, 그때 추적한 얼굴 자리를 네모로 겹쳐 보여준다.
 * 새로 저장하는 영상은 없다 — 이미 이 브라우저에 있는 녹화를 구간만 잘라 본다.
 */
export function EvidenceClip({ url, events }: EvidenceClipProps) {
  const [index, setIndex] = useState(0);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const event = events[Math.min(index, events.length - 1)];
  const from = Math.max(0, event.startMs - PAD_MS);
  const to = event.endMs + PAD_MS;

  // 구간이 바뀌면 그 지점으로 옮겨 재생하고, 끝나면 처음으로 되돌려 반복한다
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    let alive = true;

    const seekToStart = () => {
      video.currentTime = from / 1000;
      void video.play().catch(() => {});
    };
    const onTime = () => {
      if (!alive) return;
      if (video.currentTime * 1000 >= to) seekToStart();
    };
    const onReady = () => {
      if (!alive) return;
      // webm 은 길이를 모르면 탐색이 실패한다. 한 번 끝까지 갔다 오면 길이가 잡힌다.
      if (!Number.isFinite(video.duration)) {
        video.currentTime = 1e101;
        window.setTimeout(seekToStart, 150);
        return;
      }
      seekToStart();
    };

    video.addEventListener('timeupdate', onTime);
    if (video.readyState >= 1) onReady();
    else video.addEventListener('loadedmetadata', onReady, { once: true });

    return () => {
      alive = false;
      video.removeEventListener('timeupdate', onTime);
      video.removeEventListener('loadedmetadata', onReady);
    };
  }, [from, to, url]);

  return (
    <div>
      <div className="relative overflow-hidden rounded-xl bg-slate-900">
        <video className="w-full" muted playsInline ref={videoRef} src={url} />
        {event.box && (
          <>
            <span
              aria-hidden="true"
              className="pointer-events-none absolute rounded-md border-2 border-amber-400"
              style={{
                left: `${event.box.x * 100}%`,
                top: `${event.box.y * 100}%`,
                width: `${event.box.w * 100}%`,
                height: `${event.box.h * 100}%`,
              }}
            />
            <span
              className="pointer-events-none absolute rounded bg-amber-400 px-1.5 py-0.5 text-[10px] font-bold text-slate-900"
              style={{
                left: `${event.box.x * 100}%`,
                top: `calc(${event.box.y * 100}% - 18px)`,
              }}
            >
              {EVENT_META[event.kind].label}
            </span>
          </>
        )}
        <span className="pointer-events-none absolute right-2 top-2 rounded-full bg-black/60 px-2 py-0.5 text-[10px] font-semibold text-white">
          {(event.startMs / 1000).toFixed(1)}초부터 {((event.endMs - event.startMs) / 1000).toFixed(1)}초 · 반복 재생
        </span>
      </div>

      {events.length > 1 && (
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {events.slice(0, 8).map((e, i) => (
            <li key={i}>
              <button
                className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 transition ${
                  i === index
                    ? 'bg-slate-900 text-white ring-slate-900'
                    : 'bg-white text-slate-600 ring-slate-200 hover:bg-slate-100'
                }`}
                onClick={() => setIndex(i)}
                type="button"
              >
                {i + 1}번째 · {(e.startMs / 1000).toFixed(1)}초
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-1.5 text-[11px] text-slate-400">
        노란 네모가 그때 프로그램이 인식한 얼굴 자리예요. 네모가 없으면 얼굴을 찾지 못한 구간입니다.
      </p>
    </div>
  );
}

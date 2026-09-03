import { forwardRef, useEffect, useRef, type ReactNode } from 'react';
import { prefersReducedMotion } from './useInView';
import { useScrollProgress } from './useScrollProgress';

interface HeroSceneProps {
  /** 검색 폼 + 결과 (HomePage 가 상태를 들고 넘긴다) */
  search: ReactNode;
}

/** 스크럽용 영상: 키프레임 간격 6프레임·오디오 없음 (public/). */
const HERO_VIDEO_SRC = '/landing-scrub.mp4';
/** 히어로 스크롤 구간 길이 (vh). 길수록 같은 스크롤에 프레임이 천천히 넘어간다. */
const HERO_SCROLL_VH = 300;

/** 진행률 a~b 구간을 0~1 로 편다 */
const ramp = (p: number, a: number, b: number) =>
  Math.min(1, Math.max(0, (p - a) / (b - a)));

/**
 * Scene 01 — 화면을 꽉 채운 배경 영상이 스크롤에 따라 프레임이 넘어간다 (자동재생 아님).
 * 300vh 구간 안에 100vh 화면을 sticky 로 고정하고, 진행률을 영상 currentTime 에 매핑한다.
 * 문구는 진행률 구간별로 등장하고, 검색창은 후반부에 올라온다.
 * 모션 축소 설정에서는 스크럽하지 않고 첫 프레임 위에 모든 내용을 바로 보여준다.
 */
export const HeroScene = forwardRef<HTMLElement, HeroSceneProps>(function HeroScene(
  { search },
  ref,
) {
  const reduced = prefersReducedMotion();
  const [trackRef, rawProgress] = useScrollProgress<HTMLDivElement>();
  const progress = reduced ? 1 : rawProgress;
  const videoRef = useRef<HTMLVideoElement>(null);

  // 진행률 → 영상 시간. 메타데이터 전이면 duration 이 NaN 이라 건너뛴다.
  useEffect(() => {
    if (reduced) return;
    const video = videoRef.current;
    if (!video) return;
    const seek = () => {
      const duration = video.duration;
      if (!Number.isFinite(duration) || duration <= 0) return;
      // 마지막 프레임 직전까지만 (끝에 닿으면 브라우저가 검은 프레임을 보일 수 있다)
      video.currentTime = Math.min(duration - 0.05, rawProgress * duration);
    };
    if (video.readyState >= 1) seek();
    else video.addEventListener('loadedmetadata', seek, { once: true });
    return () => video.removeEventListener('loadedmetadata', seek);
  }, [rawProgress, reduced]);

  const line1 = ramp(progress, 0.02, 0.22);
  const line2 = ramp(progress, 0.28, 0.5);
  const sub = ramp(progress, 0.52, 0.7);
  const searchIn = ramp(progress, 0.68, 0.86);

  return (
    <section aria-labelledby="hero-title" ref={ref}>
      <div
        className="relative"
        ref={trackRef}
        style={{ height: reduced ? '100vh' : `${HERO_SCROLL_VH}vh` }}
      >
        <div className="sticky top-0 h-screen overflow-hidden">
          <video
            aria-label="기분 서비스 소개 영상"
            className="absolute inset-0 size-full object-cover"
            muted
            playsInline
            preload="auto"
            ref={videoRef}
            src={HERO_VIDEO_SRC}
          />
          {/* 헤더·문구 가독성용 그라데이션 */}
          <div
            aria-hidden="true"
            className="absolute inset-0 bg-gradient-to-b from-white/70 via-white/10 to-slate-950/60"
          />

          <div className="relative flex h-full flex-col items-center justify-center px-6 pt-[72px] text-center">
            <p
              className="text-sm font-bold text-blue-600"
              style={{ opacity: Math.max(0.3, line1), transform: `translateY(${(1 - line1) * 12}px)` }}
            >
              취업 준비생을 위한 기업 분석
            </p>
            <h1
              className="hero-title mt-4 font-extrabold tracking-tight text-slate-950"
              id="hero-title"
            >
              <span
                className="block"
                style={{ opacity: line1, transform: `translateY(${(1 - line1) * 24}px)` }}
              >
                기업은 숫자로 말합니다.
              </span>
              <span
                className="block text-blue-600"
                style={{ opacity: line2, transform: `translateY(${(1 - line2) * 24}px)` }}
              >
                기분은 그 변화를 읽습니다.
              </span>
            </h1>
            <p
              className="body-large mx-auto mt-6 max-w-xl text-slate-700"
              style={{ opacity: sub, transform: `translateY(${(1 - sub) * 16}px)` }}
            >
              사업보고서와 뉴스에 흩어진 기업의 신호를 한눈에 확인하세요.
            </p>

            <div
              className="mt-10 w-full max-w-2xl text-left"
              style={{
                opacity: searchIn,
                transform: `translateY(${(1 - searchIn) * 32}px)`,
                pointerEvents: searchIn > 0.5 ? 'auto' : 'none',
              }}
            >
              {search}
            </div>

            <p
              aria-hidden="true"
              className="absolute bottom-8 left-1/2 -translate-x-1/2 text-xs font-semibold text-white/90"
              style={{ opacity: 1 - ramp(progress, 0.6, 0.85) }}
            >
              스크롤해서 계속 보기
              <span className="landing-bounce ml-1 inline-block">↓</span>
            </p>
          </div>
        </div>
      </div>
    </section>
  );
});

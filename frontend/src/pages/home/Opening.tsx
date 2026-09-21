import { forwardRef, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BRAND_TAGLINE } from '../../components/layout/brand';
import { prefersReducedMotion } from '../../hooks/useInView';

/** 여기서 바로 갈 수 있는 세 곳. 기업 검색은 '기업 분석' 안에 있다 */
const ENTRIES = [
  { to: '/companies', step: '1', title: '기업 분석', desc: '회사가 무엇을 보고 무엇을 묻는지' },
  { to: '/cover-letters/new', step: '2', title: '자소서 검토', desc: '코치 다섯이 문단마다 다른 눈으로' },
  { to: '/interviews', step: '3', title: '모의 면접', desc: '답변과 말투·자세를 영상으로' },
] as const;

const HERO_VIDEO = '/landing/turn.mp4';
const HERO_POSTER = '/landing/turn.jpg';

/**
 * 카메라가 책상 건너편으로 넘어가는 시점. 그 전까지는 "내가 쓴다", 그 뒤로는 "저쪽에서 본다".
 * 영상 길이(10초)에 맞춘 값이라 영상을 바꾸면 같이 손봐야 한다.
 */
const TURN_AT_MS = 5200;

/** 넘어가기 전후로 한 줄씩. 영상이 도는 동안 글도 같이 넘어간다 */
const BEFORE = '열심히 썼습니다.';
const AFTER = '그런데 저쪽에서는 어떻게 보일까요?';

/**
 * 랜딩 첫 장.
 *
 * <p>이 서비스 이름이 "기업의 눈으로 보는 나의 Fit" 인데 정작 첫 화면에 눈이 뒤집히는 순간이
 * 없었다. 카메라가 책상을 넘어 맞은편으로 돌아가는 영상 한 편이 그 문장을 대신한다.
 * 화면이 넘어가는 그 순간에 글도 같이 바뀐다.
 *
 * <p>모션을 줄인 설정이면 영상을 돌리지 않고 첫 프레임만 깔고 뒤쪽 문장을 바로 보여준다.
 */
export const Opening = forwardRef<HTMLElement, { onNext: () => void }>(function Opening(
  { onNext },
  ref,
) {
  const still = prefersReducedMotion();
  const [turned, setTurned] = useState(still);

  useEffect(() => {
    if (still) return;
    const id = window.setTimeout(() => setTurned(true), TURN_AT_MS);
    return () => window.clearTimeout(id);
  }, [still]);

  return (
    <section
      aria-labelledby="hero-title"
      className="relative isolate snap-start overflow-hidden bg-slate-950 text-white"
      id="hero"
      ref={ref}
    >
      <div aria-hidden="true" className="absolute inset-0">
        {still ? (
          <img alt="" className="size-full object-cover" src={HERO_POSTER} />
        ) : (
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
        )}
        <div className="absolute inset-0 bg-gradient-to-b from-slate-950/75 via-slate-950/55 to-slate-950/90" />
      </div>

      <div className="relative mx-auto flex min-h-[100svh] w-full max-w-[1100px] flex-col px-6 pt-24 pb-16">
        <div className="flex flex-1 flex-col items-center justify-center text-center">
          {/* 영상이 넘어가는 순간 이 줄도 바뀐다. key 를 주면 새로 떠오른다 */}
          <p className="anim-pop text-[15px] font-semibold text-white/60" key={turned ? 'a' : 'b'}>
            {turned ? AFTER : BEFORE}
          </p>

          <h1 className="display-xl mt-4 max-w-[16ch] text-balance" id="hero-title">
            {BRAND_TAGLINE}
          </h1>
          <p className="mt-5 max-w-[42ch] text-[15px] break-keep text-white/70">
            회사가 나를 어떻게 볼지 먼저 봅니다. 기업 분석에서 시작해 자소서와 면접까지 같은
            기준으로 이어집니다.
          </p>

          <div className="mt-9 flex flex-wrap justify-center gap-3">
            <Link
              className="rounded-full bg-white px-7 py-3.5 text-base font-bold text-slate-950 transition hover:-translate-y-0.5 hover:shadow-lg"
              to="/companies"
            >
              기업 분석 시작하기
            </Link>
            <Link
              className="rounded-full px-7 py-3.5 text-base font-bold text-white/80 ring-1 ring-white/25 transition hover:-translate-y-0.5 hover:bg-white/10 hover:text-white"
              to="/cover-letters/new"
            >
              로그인 없이 자소서 써 보기
            </Link>
          </div>
        </div>

        {/*
          여기서 뭘 할 수 있는지가 첫 화면에 있어야 한다. 기업 목록은 기업 분석 첫 화면이
          이미 보여주므로 랜딩은 세 기능만 세운다.
        */}
        <ul aria-label="바로 가기" className="mx-auto grid w-full max-w-4xl gap-2 sm:grid-cols-3">
          {ENTRIES.map((entry) => (
            <li key={entry.to}>
              <Link
                className="flex h-full items-start gap-3 rounded-xl bg-white/10 px-4 py-3 ring-1 ring-white/20 backdrop-blur transition hover:-translate-y-0.5 hover:bg-white hover:text-slate-950 hover:ring-white"
                to={entry.to}
              >
                <span
                  aria-hidden="true"
                  className="mt-0.5 text-[12px] font-extrabold opacity-50"
                >
                  0{entry.step}
                </span>
                <span className="min-w-0">
                  <span className="block text-[14px] font-extrabold">{entry.title}</span>
                  <span className="mt-0.5 block text-[12px] break-keep opacity-60">{entry.desc}</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>

        <button
          className="mx-auto mt-8 text-[13px] font-semibold text-white/50 transition hover:text-white"
          onClick={onNext}
          type="button"
        >
          코치들이 어떻게 봐 주는지 ↓
        </button>
      </div>
    </section>
  );
});

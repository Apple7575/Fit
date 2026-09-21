import { forwardRef } from 'react';
import { Link } from 'react-router-dom';
import { BRAND_TAGLINE } from '../../components/layout/brand';
import { prefersReducedMotion } from '../../hooks/useInView';

/** 여기서 바로 갈 수 있는 세 곳. 기업 검색은 '기업 분석' 안에 있다 */
const ENTRIES = [
  { to: '/companies', step: '1', title: '기업 분석' },
  { to: '/cover-letters/new', step: '2', title: '자소서 검토' },
  { to: '/interviews', step: '3', title: '모의 면접' },
] as const;

const HERO_VIDEO = '/landing/turn.mp4';
const HERO_POSTER = '/landing/turn.jpg';

/**
 * 랜딩 첫 장.
 *
 * <p>이 서비스 이름이 "기업의 눈으로 보는 나의 Fit" 인데 정작 첫 화면에 눈이 뒤집히는 순간이
 * 없었다. 카메라가 책상을 넘어 맞은편으로 돌아가는 영상 한 편이 그 문장을 대신한다.
 * 한때 그 순간에 맞춰 바뀌는 글줄을 얹었지만, 첫 화면에 글이 많아 덜어냈다. 영상만 남긴다.
 *
 * <p>모션을 줄인 설정이면 영상을 돌리지 않고 첫 프레임만 깐다.
 */
export const Opening = forwardRef<HTMLElement, { onNext: () => void }>(function Opening(
  { onNext },
  ref,
) {
  const still = prefersReducedMotion();

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
          <h1 className="display-xl max-w-[16ch] text-balance" id="hero-title">
            {BRAND_TAGLINE}
          </h1>
          {/* 두 줄로 읽히길 바라는 자리라, 폭에 따라 흔들리지 않게 줄바꿈을 못 박는다 */}
          <p className="mt-5 max-w-[42ch] text-[15px] break-keep text-white/70">
            회사가 나를 어떻게 볼지 먼저 봅니다.
            <br />
            감이 아니라, 근거로요.
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

          카드 석 장에 설명까지 달려 있으면 첫 화면이 글로 꽉 찬다. 화살표로 이어 붙인 한 줄로
          바꾼다. "같은 기준으로 이어집니다" 를 문장으로 쓰는 대신 모양으로 보여주는 셈이라,
          위 부제에서 그 문장을 덜어낼 수 있었다.
        */}
        {/* 이름표는 목록에 둔다. nav 로 감싸 옮겼더니 목록의 접근성 이름이 사라졌다 */}
        <ol
          aria-label="바로 가기"
          className="mx-auto flex flex-wrap items-center justify-center gap-x-1 gap-y-2"
        >
          {/* 화살표를 뒤따르는 칸과 한 덩어리로 묶는다. 좁은 화면에서 줄이 바뀔 때
              화살표만 줄 끝에 남지 않고 다음 줄 앞머리로 함께 넘어간다 */}
          {ENTRIES.map((entry, i) => (
            <li className="flex items-center gap-1" key={entry.to}>
              {i > 0 && (
                <span aria-hidden="true" className="px-1 text-white/30">
                  →
                </span>
              )}
              <Link
                className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-bold text-white/75 ring-1 ring-white/20 backdrop-blur transition hover:-translate-y-0.5 hover:bg-white hover:text-slate-950 hover:ring-white"
                to={entry.to}
              >
                <span aria-hidden="true" className="text-[11px] font-extrabold opacity-50">
                  0{entry.step}
                </span>
                {entry.title}
              </Link>
            </li>
          ))}
        </ol>

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

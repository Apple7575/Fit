import { Link } from 'react-router-dom';
import { CharacterSlot } from '../../components/brand/CharacterSlot';
import { COACHES } from '../../components/brand/characters';
import { useInView } from '../../hooks/useInView';
import { FEATURED_COMPANIES } from './featuredCompanies';

interface FinalCtaProps {
  /** "지금 시작하기" — 히어로 검색창으로 스냅·포커스 */
  onStart: () => void;
}

/** 검색창에 회사 이름을 치는 손. 이 장이 시키는 동작이 화면 뒤에서 이미 일어나고 있다 */
const START_VIDEO = '/landing/start.mp4';
const START_POSTER = '/landing/start.jpg';

/**
 * 마지막 한 장. 코치 다섯이 늘어서고, 시작 버튼과 바로 볼 수 있는 기업.
 *
 * <p>앞 세 장이 모두 영상 위 어두운 전면인데 이 장만 회색 바탕에 흰 카드가 떠 있어서
 * 혼자 따로 놀았다. 배경도 레이아웃 문법도 앞 장들에 맞추고, 카드는 걷어낸다.
 */
export function FinalCta({ onStart }: FinalCtaProps) {
  const [ref, inView] = useInView<HTMLDivElement>({ threshold: 0.3 });

  return (
    <section
      aria-labelledby="cta-title"
      className="relative isolate snap-start flex min-h-screen flex-col justify-center overflow-hidden bg-slate-950 pt-14 text-white"
      id="start"
    >
      <div aria-hidden="true" className="absolute inset-0">
        {/*
          영상 속 자동완성 목록은 실제 회사 이름이 아니라 만들어진 글자다. 읽히면 안 되고,
          읽을 것도 아니다. 살짝 흐리게 해서 "검색하는 화면"이라는 형태만 남긴다.
          (흐리면 가장자리가 비므로 조금 키운다)
        */}
        <video
          autoPlay
          className="size-full scale-105 object-cover blur-[3px]"
          loop
          muted
          playsInline
          poster={START_POSTER}
          preload="metadata"
          src={START_VIDEO}
        />
        {/* 노트북 화면이 밝아서 글씨와 싸운다. 앞 장들보다 조금 더 눌러 준다 */}
        <div className="absolute inset-0 bg-gradient-to-br from-slate-950/92 via-slate-950/84 to-slate-950/94" />
      </div>

      <div className="relative mx-auto flex w-full max-w-[1200px] flex-1 items-center px-6 py-16">
        <div className="reveal w-full text-center" data-inview={inView} ref={ref}>
          <ul aria-label="코치 다섯" className="mb-8 flex items-end justify-center gap-2 sm:gap-4">
            {COACHES.map((coach, i) => (
              <li key={coach.key} style={{ transform: `translateY(${i % 2 ? 0 : 10}px)` }}>
                <CharacterSlot character={coach.key} size={i === 2 ? 96 : 76} />
              </li>
            ))}
          </ul>
          <h2 className="display-lg text-balance" id="cta-title">
            궁금한 회사부터 시작해 보세요.
          </h2>
          <p className="mt-4 break-keep text-white/70">
            기업명을 검색하면 분석이 시작되고, 자소서와 면접까지 코치들이 따라옵니다.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <button
              className="rounded-full bg-white px-8 py-3.5 text-base font-bold text-slate-950 transition hover:-translate-y-0.5 hover:shadow-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white"
              onClick={onStart}
              type="button"
            >
              지금 시작하기
            </button>
            <Link
              className="rounded-full px-8 py-3.5 text-base font-bold text-white/80 ring-1 ring-white/25 transition hover:-translate-y-0.5 hover:bg-white/10 hover:text-white"
              to="/cover-letters/new"
            >
              로그인 없이 자소서 써 보기
            </Link>
          </div>
          <ul aria-label="분석 가능한 기업" className="mt-8 flex flex-wrap justify-center gap-2">
            {FEATURED_COMPANIES.map((company) => (
              <li key={company.corpCode}>
                <Link
                  className="inline-block rounded-full px-4 py-1.5 text-sm font-semibold text-white/75 ring-1 ring-white/20 transition hover:bg-white/10 hover:text-white"
                  to={`/companies/${company.corpCode}/overview`}
                >
                  {company.name}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

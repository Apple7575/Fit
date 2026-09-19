import { Link } from 'react-router-dom';
import { CharacterSlot } from '../../components/brand/CharacterSlot';
import type { CharacterKey } from '../../components/brand/characters';
import { useInView } from '../../hooks/useInView';

/** 가운데(제일 큰 자리)에 핑크가 서도록 늘어세운 코치 다섯 */
const LINEUP: readonly CharacterKey[] = ['hamster', 'otter', 'fox', 'owl', 'chick'];

interface PrepCtaProps {
  corpName: string | null;
}

/**
 * 요약의 마지막 장. 이 회사를 기준으로 자소서 검토·모의 면접으로 넘어가는 문.
 * (자소서·면접 화면이 기업 미리 선택을 받게 되면 corpCode 를 실어 보낸다)
 */
export function PrepCta({ corpName }: PrepCtaProps) {
  const [ref, inView] = useInView<HTMLElement>({ threshold: 0.3 });
  return (
    <section
      aria-labelledby="prep-cta-title"
      className="reveal relative overflow-hidden rounded-[1.75rem] bg-slate-950 px-6 py-10 text-center text-white sm:px-12"
      data-inview={inView}
      ref={ref}
    >
      <div aria-hidden="true" className="image-fallback absolute inset-0 opacity-90" />
      <div className="relative">
        <ul aria-label="코치 다섯" className="mb-6 flex items-end justify-center gap-2 sm:gap-4">
          {LINEUP.map((key, i) => (
            <li
              className="reveal"
              data-inview={inView}
              key={key}
              style={{ '--reveal-delay': `${i * 80}ms`, transform: `translateY(${i % 2 ? 0 : 8}px)` } as never}
            >
              <CharacterSlot character={key} size={i === 2 ? 84 : 64} />
            </li>
          ))}
        </ul>
        <h2 className="display-lg text-balance" id="prep-cta-title">
          {corpName ? `${corpName}, ` : ''}함께 준비해 볼까요?
        </h2>
        <p className="mt-3 text-white/70">
          위 세 가지를 코치들이 자소서와 면접에서 그대로 물어봐요.
        </p>
        <div className="mt-7 flex flex-wrap justify-center gap-3">
          <Link
            className="rounded-full bg-white px-7 py-3 text-base font-bold text-slate-950 transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-lift)]"
            to="/cover-letters/new"
          >
            자소서 검토 받기
          </Link>
          <Link
            className="rounded-full bg-white/10 px-7 py-3 text-base font-bold text-white ring-1 ring-white/30 backdrop-blur transition hover:-translate-y-0.5 hover:bg-white/20"
            to="/interviews/new"
          >
            모의 면접 보기
          </Link>
        </div>
      </div>
    </section>
  );
}

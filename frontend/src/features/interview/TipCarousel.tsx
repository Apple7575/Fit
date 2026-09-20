import { useEffect, useState } from 'react';
import { StepText } from '../../components/brand/LoadingScreen';
import { prefersReducedMotion } from '../../hooks/useInView';
import { GuideImage } from './GuideImage';
import { INTERVIEW_TIPS } from './interviewTips';
import { CARD, T } from './reportTokens';

/** 한 장을 읽기에 넉넉한 시간. 더 짧으면 읽다가 넘어간다 */
const HOLD_MS = 6000;

/**
 * 기다리는 동안 넘겨 보는 면접 팁.
 *
 * <p>분석은 최대 1분 걸린다. 그 시간을 버리지 않으려고 바로 다음 면접에 쓸 것을 한 장씩 띄운다.
 * 진행 상태가 아니라 읽을거리이므로 끝에서 처음으로 돌아간다(로딩 문구와 달리 멈추지 않는다).
 * 모션을 줄인 환경에서는 넘기지 않고 첫 장만 둔다.
 */
export function TipCarousel({
  className = '',
  /** 지금 무엇을 하는 중인지. 주면 팁 위에 한 줄로 붙는다 */
  message,
}: {
  className?: string;
  message?: string[];
}) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (prefersReducedMotion()) return;
    const id = window.setInterval(
      () => setIndex((i) => (i + 1) % INTERVIEW_TIPS.length),
      HOLD_MS,
    );
    return () => window.clearInterval(id);
  }, []);

  const tip = INTERVIEW_TIPS[index];

  return (
    <section aria-labelledby="tip-title" className={`mx-auto w-full max-w-md ${className}`}>
      {/*
        기다림은 한 덩어리여야 한다. 돌멩이가 뛰는 화면 아래에 팁 카드를 또 쌓으면 눈이
        갈라진다. 진행 상황은 팁 위에 한 줄로만 둔다.
      */}
      {message && (
        <div aria-busy="true" aria-live="polite" className="mb-6 text-center" role="status">
          <StepText onDark={false} steps={message} />
        </div>
      )}
      <p className={`text-center ${T.label}`} id="tip-title">
        기다리는 동안 — 면접 팁
      </p>
      <div className={`mt-3 overflow-hidden ${CARD}`}>
        {/* key 를 주면 장이 바뀔 때마다 새로 붙어 다시 떠오른다 */}
        <div className="anim-pop" key={tip.image}>
          <GuideImage alt="" className="aspect-[16/10] w-full object-cover" name={tip.image} />
          <div className="p-4 text-center">
            <p className={T.bodyStrong}>{tip.title}</p>
            <p className={`mt-1 break-keep ${T.body}`}>{tip.body}</p>
          </div>
        </div>
      </div>

      {/* 몇 장 중 몇 번째인지. 누를 수 있는 것이 아니라 장식이다 */}
      <ul aria-hidden="true" className="mt-3 flex justify-center gap-1.5">
        {INTERVIEW_TIPS.map((t, i) => (
          <li
            className={`h-1.5 rounded-full transition-all ${
              i === index ? 'w-5 bg-slate-500' : 'w-1.5 bg-slate-300'
            }`}
            key={t.image}
          />
        ))}
      </ul>
    </section>
  );
}

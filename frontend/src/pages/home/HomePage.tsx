import { useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { SiteHeader } from '../../components/layout/SiteHeader';
import { prefersReducedMotion } from '../../hooks/useInView';
import { AgentDemo } from './AgentDemo';
import { FinalCta } from './FinalCta';
import { Hero } from './Hero';
import { InterviewDemo } from './InterviewDemo';
import { SectionDots } from './SectionDots';

const SECTIONS = [
  { id: 'hero', label: '시작' },
  { id: 'agents', label: '코치 다섯' },
  { id: 'interview', label: 'AI 면접' },
  { id: 'start', label: '시작하기' },
];

/**
 * 홈 = 랜딩. 한 화면 한 장씩 스냅 스크롤로 넘어간다:
 * 소개와 바로 가기 → 멀티 에이전트 검토 방 → AI 면접 → 시작하기.
 * 기업 검색은 '기업 분석'(/companies) 이 맡으므로 랜딩에는 검색창을 두지 않는다.
 */
export function HomePage() {
  const navigate = useNavigate();
  const heroRef = useRef<HTMLElement>(null);
  const scrollerRef = useRef<HTMLElement>(null);

  const behavior = () => (prefersReducedMotion() ? 'auto' : 'smooth') as ScrollBehavior;

  const goNext = useCallback(() => {
    scrollerRef.current
      ?.querySelector<HTMLElement>('#agents')
      ?.scrollIntoView?.({ behavior: behavior(), block: 'start' });
  }, []);

  return (
    <div className="relative h-screen overflow-hidden bg-slate-50">
      {/* 첫 장 위에 흰 유리 헤더로 떠 있는다. 아래 섹션들이 헤더 높이만큼 위 여백을 갖는다 */}
      <SiteHeader overlay scrolled showSearch={false} />

      {/* 화면 높이 그대로 한 장씩 스냅. 각 섹션이 헤더 높이(3.5rem) 만큼 위 여백을 가진다 */}
      <main className="h-screen snap-y snap-mandatory overflow-y-auto scroll-smooth" ref={scrollerRef}>
        <Hero onNext={goNext} ref={heroRef} />
        <AgentDemo />
        <InterviewDemo />
        <FinalCta onStart={() => navigate('/companies')} />
      </main>

      <SectionDots container={scrollerRef} sections={SECTIONS} />
    </div>
  );
}

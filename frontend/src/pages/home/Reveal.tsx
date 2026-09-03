import type { ReactNode } from 'react';
import { useInView } from './useInView';

interface RevealProps {
  children: ReactNode;
  className?: string;
  /** 등장 지연(ms). 여러 요소를 순차 등장시킬 때 */
  delay?: number;
  as?: 'div' | 'p' | 'li' | 'section' | 'article';
}

/**
 * 뷰포트에 들어오면 아래에서 떠오르며 나타난다 (Rise). 모션 축소 설정·관찰 불가 환경에서는
 * 처음부터 보이므로 내용 접근성에 영향이 없다.
 */
export function Reveal({ children, className = '', delay = 0, as = 'div' }: RevealProps) {
  const [ref, inView] = useInView<HTMLDivElement>();
  const Tag = as;
  return (
    <Tag
      className={`landing-reveal ${inView ? 'is-visible' : ''} ${className}`}
      ref={ref as never}
      style={delay ? { transitionDelay: `${delay}ms` } : undefined}
    >
      {children}
    </Tag>
  );
}

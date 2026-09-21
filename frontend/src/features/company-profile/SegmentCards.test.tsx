import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { ProfileSegment } from './types';
import { SegmentCard } from './SegmentCard';
import { SegmentRevenueCard } from './SegmentRevenueCard';

const segments: ProfileSegment[] = [
  { code: 'DS', revenue: 232000000000000, revenueShare: 58.0 },
  { code: 'DX', revenue: 168000000000000, revenueShare: 42.0 },
  { code: 'SDC', revenue: null, revenueShare: null },
];

describe('SegmentCard', () => {
  it('사업부 코드와 매출을 보여주고 미공시 매출은 "미공시" 로 표시한다', () => {
    render(<SegmentCard segments={segments} />);

    expect(screen.getByRole('heading', { name: '사업부' })).toBeInTheDocument();
    expect(screen.getAllByText('DS').length).toBeGreaterThan(0);
    expect(screen.getByText(/232조/)).toBeInTheDocument();
    expect(screen.getByText('미공시')).toBeInTheDocument();
  });
});

describe('SegmentRevenueCard', () => {
  it('공시 부문만 도넛에 그리고 전체 매출을 가운데에 보여준다', () => {
    render(
      <SegmentRevenueCard
        segments={segments}
        totalRevenue={400000000000000}
      />,
    );

    expect(
      screen.getByRole('heading', { name: '사업부 매출' }),
    ).toBeInTheDocument();
    expect(screen.getByText(/400조/)).toBeInTheDocument();
    expect(screen.getByText('58.0%')).toBeInTheDocument();
    expect(screen.getByText('42.0%')).toBeInTheDocument();
    // 미공시 부문은 범례에 "미공시" 로 남는다
    expect(screen.getByText('미공시')).toBeInTheDocument();
    // 도넛 호는 공시 부문 2개만
    expect(
      document.querySelectorAll('[data-testid="donut-arc"]'),
    ).toHaveLength(2);
  });

  it('매출이 음수인 항목은 호에서 빼고 범례에는 값 그대로 남긴다', () => {
    // 연결 조정처럼 빼는 몫이 음수로 공시된다. 음수 길이는 stroke-dasharray 를 통째로
    // 무효로 만들어 그 조각이 원 하나를 꽉 채우고 앞의 조각들을 전부 덮어 버렸다
    render(
      <SegmentRevenueCard
        segments={[
          { code: 'DX', revenue: 187000000000000, revenueShare: 56.3 },
          { code: 'DS', revenue: 130000000000000, revenueShare: 39.0 },
          { code: '기타', revenue: -30000000000000, revenueShare: -9.0 },
        ]}
        totalRevenue={333000000000000}
      />,
    );

    // 호는 양수 둘만
    const arcs = [...document.querySelectorAll('[data-testid="donut-arc"]')];
    expect(arcs).toHaveLength(2);
    // 길이가 음수인 호는 하나도 없다
    expect(
      arcs.every((arc) => !(arc.getAttribute('stroke-dasharray') ?? '').startsWith('-')),
    ).toBe(true);
    // 두 호가 원을 정확히 채운다
    const total = arcs.reduce(
      (acc, arc) => acc + Number((arc.getAttribute('stroke-dasharray') ?? '0').split(' ')[0]),
      0,
    );
    expect(total).toBeCloseTo(100, 5);

    // 범례에는 음수 항목도 공시된 비중 그대로 남는다
    expect(screen.getByText('기타')).toBeInTheDocument();
    expect(screen.getByText('-9.0%')).toBeInTheDocument();
    expect(screen.getByText(/그래프에서 빼고/)).toBeInTheDocument();
  });

  it('공시 부문이 하나도 없으면 왜 없는지 알려 준다', () => {
    const { container } = render(
      <SegmentRevenueCard
        segments={[{ code: 'A', revenue: null, revenueShare: null }]}
        totalRevenue={null}
      />,
    );

    expect(container).not.toBeEmptyDOMElement();
    expect(screen.getByText(/사업부별 매출을 공시하지 않는 기업/)).toBeInTheDocument();
  });
});

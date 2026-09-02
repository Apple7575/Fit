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
  it('공시 부문만 도넣에 그리고 전체 매출을 가운데에 보여준다', () => {
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
    // 도넗 호는 공시 부문 2개만
    expect(
      document.querySelectorAll('[data-testid="donut-arc"]'),
    ).toHaveLength(2);
  });

  it('공시 부문이 하나도 없으면 아무것도 렌더하지 않는다', () => {
    const { container } = render(
      <SegmentRevenueCard
        segments={[{ code: 'A', revenue: null, revenueShare: null }]}
        totalRevenue={null}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});

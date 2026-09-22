import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { CoverLetterSummary } from '../cover-letter/types';
import { CoverLetterSwitcher } from './CoverLetterSwitcher';

const letter = (id: number, title: string): CoverLetterSummary => ({
  id,
  title,
  targetCompany: null,
  targetPosition: null,
  itemCount: 1,
  updatedAt: '2026-09-22T00:00:00Z',
});

const letters = [
  letter(1, '2026 상반기 인턴 지원 자소서'),
  letter(2, '현대엘리베이터 자소서'),
  letter(3, 'kt알파 데이터 분석가'),
];

const openList = () => {
  fireEvent.click(screen.getByRole('button', { name: '검토할 자소서' }));
};

describe('CoverLetterSwitcher', () => {
  it('shows the picked cover letter on the button', () => {
    render(<CoverLetterSwitcher letters={letters} onSelect={vi.fn()} selectedId={2} />);

    expect(screen.getByRole('button', { name: '검토할 자소서' })).toHaveTextContent(
      '현대엘리베이터 자소서',
    );
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });

  it('lists every cover letter once opened', () => {
    render(<CoverLetterSwitcher letters={letters} onSelect={vi.fn()} selectedId={1} />);

    openList();

    expect(screen.getAllByRole('option')).toHaveLength(3);
    expect(screen.getByRole('option', { name: /현대엘리베이터/ })).toBeInTheDocument();
  });

  it('marks the picked one as selected', () => {
    render(<CoverLetterSwitcher letters={letters} onSelect={vi.fn()} selectedId={3} />);

    openList();

    expect(screen.getByRole('option', { name: /kt알파/ })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('option', { name: /현대엘리베이터/ })).toHaveAttribute(
      'aria-selected',
      'false',
    );
  });

  it('hands over the id that was clicked', () => {
    const onSelect = vi.fn();
    render(<CoverLetterSwitcher letters={letters} onSelect={onSelect} selectedId={1} />);

    openList();
    // 줄은 mousedown 으로 고른다 — 초점이 빠지면서 목록이 먼저 접히기 때문이다
    fireEvent.mouseDown(screen.getByRole('option', { name: /현대엘리베이터/ }));

    expect(onSelect).toHaveBeenCalledWith(2);
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });

  it('walks the list with the arrow keys and picks with enter', () => {
    const onSelect = vi.fn();
    render(<CoverLetterSwitcher letters={letters} onSelect={onSelect} selectedId={1} />);

    const trigger = screen.getByRole('button', { name: '검토할 자소서' });
    fireEvent.keyDown(trigger, { key: 'ArrowDown' });
    fireEvent.keyDown(trigger, { key: 'ArrowDown' });
    fireEvent.keyDown(trigger, { key: 'Enter' });

    expect(onSelect).toHaveBeenCalledWith(2);
  });

  it('closes on escape without picking', () => {
    const onSelect = vi.fn();
    render(<CoverLetterSwitcher letters={letters} onSelect={onSelect} selectedId={1} />);

    openList();
    fireEvent.keyDown(screen.getByRole('button', { name: '검토할 자소서' }), { key: 'Escape' });

    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(onSelect).not.toHaveBeenCalled();
  });
});

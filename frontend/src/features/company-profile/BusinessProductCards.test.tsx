import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { BusinessCard } from './BusinessCard';
import { ProductCard } from './ProductCard';

describe('BusinessCard', () => {
  it('주요 사업명을 모두 보여준다', () => {
    render(<BusinessCard items={['반도체', '스마트폰', '가전']} />);

    expect(
      screen.getByRole('heading', { name: '주요 사업' }),
    ).toBeInTheDocument();
    expect(screen.getByText('반도체')).toBeInTheDocument();
    expect(screen.getByText('스마트폰')).toBeInTheDocument();
    expect(screen.getByText('가전')).toBeInTheDocument();
  });
});

describe('ProductCard', () => {
  it('주요 제품명을 모두 보여준다', () => {
    render(<ProductCard items={['HBM', 'DRAM', 'NAND']} />);

    expect(
      screen.getByRole('heading', { name: '주요 제품' }),
    ).toBeInTheDocument();
    expect(screen.getByText('HBM')).toBeInTheDocument();
    expect(screen.getByText('DRAM')).toBeInTheDocument();
    expect(screen.getByText('NAND')).toBeInTheDocument();
  });
});

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { CompanySearchForm } from './CompanySearchForm';

describe('CompanySearchForm', () => {
  it('renders an accessible search input and search button', () => {
    render(<CompanySearchForm />);

    expect(screen.getByLabelText('기업명')).toBeInTheDocument();
    expect(screen.getByRole('searchbox', { name: '기업명' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '검색' })).toBeInTheDocument();
  });

  it('disables the search button while the keyword is empty', () => {
    render(<CompanySearchForm />);

    expect(screen.getByRole('button', { name: '검색' })).toBeDisabled();
  });

  it('keeps the search button disabled for whitespace-only keywords', () => {
    render(<CompanySearchForm />);

    fireEvent.change(screen.getByLabelText('기업명'), {
      target: { value: '   ' },
    });

    expect(screen.getByRole('button', { name: '검색' })).toBeDisabled();
  });

  it('enables the search button once a keyword is typed', () => {
    render(<CompanySearchForm />);

    fireEvent.change(screen.getByLabelText('기업명'), {
      target: { value: '삼성전자' },
    });

    expect(screen.getByRole('button', { name: '검색' })).toBeEnabled();
  });

  it('submits the trimmed keyword', () => {
    const onSearch = vi.fn();
    render(<CompanySearchForm onSearch={onSearch} />);

    fireEvent.change(screen.getByLabelText('기업명'), {
      target: { value: '  삼성전자  ' },
    });
    fireEvent.click(screen.getByRole('button', { name: '검색' }));

    expect(onSearch).toHaveBeenCalledWith('삼성전자');
  });

  it('does not submit an empty keyword', () => {
    const onSearch = vi.fn();
    render(<CompanySearchForm onSearch={onSearch} />);

    fireEvent.submit(screen.getByRole('search'));

    expect(onSearch).not.toHaveBeenCalled();
  });
});

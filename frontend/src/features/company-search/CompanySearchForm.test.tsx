import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Company } from '../../types/company';
import { searchCompanies } from './api';
import { CompanySearchForm } from './CompanySearchForm';

vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  searchCompanies: vi.fn(),
}));

const mockedSearch = vi.mocked(searchCompanies);

const company = (corpCode: string, corpName: string): Company => ({
  corpCode,
  corpName,
  stockCode: null,
  industryCode: null,
  industryName: null,
});

/** 글자를 치면 서버가 이것을 돌려준다고 두고, 칸 아래 추천만 본다 */
const answerWith = (...items: Company[]) => {
  mockedSearch.mockResolvedValue({ items, total: items.length });
};

const type = (value: string) => {
  fireEvent.change(screen.getByLabelText('기업명'), { target: { value } });
};

afterEach(() => {
  mockedSearch.mockReset();
});

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

  it('suggests companies under the box while typing', async () => {
    answerWith(company('00126380', '삼성전자'), company('00877059', '삼성바이오로직스'));
    render(<CompanySearchForm />);

    type('삼');

    expect(await screen.findByRole('option', { name: /삼성전자/ })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /삼성바이오로직스/ })).toBeInTheDocument();
    expect(mockedSearch).toHaveBeenCalledWith('삼', expect.anything());
  });

  it('puts names that start with the keyword first', async () => {
    answerWith(company('00111111', '한국삼공'), company('00126380', '삼성전자'));
    render(<CompanySearchForm />);

    type('삼');

    await screen.findByRole('option', { name: /삼성전자/ });
    expect(screen.getAllByRole('option').map((option) => option.textContent)).toEqual([
      expect.stringContaining('삼성전자'),
      expect.stringContaining('한국삼공'),
    ]);
  });

  it('hands the picked company over instead of searching', async () => {
    const onPick = vi.fn();
    const onSearch = vi.fn();
    answerWith(company('00126380', '삼성전자'));
    render(<CompanySearchForm onPick={onPick} onSearch={onSearch} />);

    type('삼');
    // 목록의 줄은 mousedown 으로 고른다 — 초점이 빠지면서 목록이 먼저 접히기 때문이다
    fireEvent.mouseDown(await screen.findByRole('option', { name: /삼성전자/ }));

    expect(onPick).toHaveBeenCalledWith(expect.objectContaining({ corpCode: '00126380' }));
    expect(onSearch).not.toHaveBeenCalled();
  });

  it('retries in hangul when the keyboard was left in english', async () => {
    mockedSearch
      .mockResolvedValueOnce({ items: [], total: 0 })
      .mockResolvedValueOnce({ items: [company('00126380', '삼성전자')], total: 1 });
    render(<CompanySearchForm />);

    type('tka');

    expect(await screen.findByRole('option', { name: /삼성전자/ })).toBeInTheDocument();
    expect(mockedSearch).toHaveBeenNthCalledWith(1, 'tka', expect.anything());
    expect(mockedSearch).toHaveBeenNthCalledWith(2, '삼', expect.anything());
    // 무엇을 바꿔 찾았는지 목록 맨 위에 적어 둔다
    expect(screen.getByRole('listbox')).toHaveTextContent('tka');
    expect(screen.getByRole('listbox')).toHaveTextContent('삼');
  });

  it('does not retry in hangul when the keyword already found something', async () => {
    answerWith(company('00126380', '삼성전자'));
    render(<CompanySearchForm />);

    type('tka');

    await screen.findByRole('option', { name: /삼성전자/ });
    expect(mockedSearch).toHaveBeenCalledTimes(1);
  });

  it('keeps the box quiet until something is typed', () => {
    render(<CompanySearchForm />);

    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(mockedSearch).not.toHaveBeenCalled();
  });
});

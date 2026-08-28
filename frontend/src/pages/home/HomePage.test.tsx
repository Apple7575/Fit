import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MOCK_ERROR_KEYWORD } from '../../mocks/companies';
import { HomePage } from './HomePage';

const search = (keyword: string) => {
  fireEvent.change(screen.getByLabelText('기업명'), {
    target: { value: keyword },
  });
  fireEvent.click(screen.getByRole('button', { name: '검색' }));
};

describe('HomePage', () => {
  it('shows no result panel before searching', () => {
    render(<HomePage />);

    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.queryByRole('list')).not.toBeInTheDocument();
  });

  it('shows a loading state and then the matched companies', async () => {
    render(<HomePage />);

    search('삼성');

    expect(screen.getByRole('status')).toHaveTextContent('검색 중입니다');

    expect(
      await screen.findByRole('button', { name: /삼성전자/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /삼성바이오로직스/ }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('finds a company by its code', async () => {
    render(<HomePage />);

    search('000660');

    expect(
      await screen.findByRole('button', { name: /SK하이닉스/ }),
    ).toBeInTheDocument();
  });

  it('shows an empty message when nothing matches', async () => {
    render(<HomePage />);

    search('없는기업');

    expect(await screen.findByText(/검색 결과가 없습니다/)).toBeInTheDocument();
  });

  it('shows an error state when the search fails', async () => {
    render(<HomePage />);

    search(MOCK_ERROR_KEYWORD);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      '검색 중 문제가 발생했습니다',
    );
    expect(screen.getByRole('button', { name: '다시 시도' })).toBeInTheDocument();
  });
});

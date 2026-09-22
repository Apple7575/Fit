import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import { AuthProvider, useAuth } from './AuthProvider';
import * as authApi from './api';

vi.mock('./api');

const mockedApi = vi.mocked(authApi);

function Probe() {
  const { user, loading, login, logout, withdraw } = useAuth();
  return (
    <div>
      <span data-testid="state">
        {loading ? 'loading' : user ? user.nickname : 'anonymous'}
      </span>
      <button onClick={() => login('a@b.com', 'secret12')} type="button">
        login
      </button>
      <button onClick={() => logout()} type="button">
        logout
      </button>
      <button onClick={() => withdraw('secret12')} type="button">
        withdraw
      </button>
    </div>
  );
}

const renderProbe = () =>
  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );

describe('AuthProvider', () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it('restores the session on mount', async () => {
    mockedApi.fetchMe.mockResolvedValue({ id: 1, email: 'a@b.com', nickname: '민재' });

    renderProbe();

    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('민재'));
  });

  it('treats a 401 on mount as anonymous', async () => {
    mockedApi.fetchMe.mockRejectedValue(new ApiError(401, 'UNAUTHENTICATED', '로그인이 필요합니다.'));

    renderProbe();

    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('anonymous'));
  });

  it('sets the user after login and clears it after logout', async () => {
    mockedApi.fetchMe.mockRejectedValue(new ApiError(401, 'UNAUTHENTICATED', ''));
    mockedApi.login.mockResolvedValue({ id: 1, email: 'a@b.com', nickname: '민재' });
    mockedApi.logout.mockResolvedValue(null);

    renderProbe();
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('anonymous'));

    await userEvent.click(screen.getByRole('button', { name: 'login' }));
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('민재'));

    await userEvent.click(screen.getByRole('button', { name: 'logout' }));
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('anonymous'));
  });

  it('clears the user even when the logout request fails', async () => {
    mockedApi.fetchMe.mockRejectedValue(new ApiError(401, 'UNAUTHENTICATED', ''));
    mockedApi.login.mockResolvedValue({ id: 1, email: 'a@b.com', nickname: '민재' });
    mockedApi.logout.mockRejectedValue(new ApiError(0, 'NETWORK_ERROR', '서버에 연결할 수 없습니다.'));

    renderProbe();
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('anonymous'));

    await userEvent.click(screen.getByRole('button', { name: 'login' }));
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('민재'));

    await userEvent.click(screen.getByRole('button', { name: 'logout' }));
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('anonymous'));
  });

  it('clears the user after withdrawal succeeds', async () => {
    mockedApi.fetchMe.mockResolvedValue({ id: 1, email: 'a@b.com', nickname: '민재' });
    mockedApi.withdraw.mockResolvedValue(null);

    renderProbe();
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('민재'));

    await userEvent.click(screen.getByRole('button', { name: 'withdraw' }));

    expect(mockedApi.withdraw).toHaveBeenCalledWith('secret12');
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('anonymous'));
  });
});

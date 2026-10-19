import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { LoginPage } from '../pages/LoginPage';
import { dataSource } from '../services';

vi.mock('../services', () => ({
  dataSource: {
    login: vi.fn(),
  },
}));

describe('LoginForm Component', () => {
  const onLoginSuccess = vi.fn();
  const onNavigateToRegister = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders login form with username, password, and remember me fields', () => {
    render(
      <LoginPage
        onLoginSuccess={onLoginSuccess}
        onNavigateToRegister={onNavigateToRegister}
      />
    );

    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/enter your password/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/remember me/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in to platform/i })).toBeInTheDocument();
  });

  it('validates required fields when submitted empty', async () => {
    render(
      <LoginPage
        onLoginSuccess={onLoginSuccess}
        onNavigateToRegister={onNavigateToRegister}
      />
    );

    const submitBtn = screen.getByRole('button', { name: /sign in to platform/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/username is required/i)).toBeInTheDocument();
      expect(screen.getByText(/password is required/i)).toBeInTheDocument();
    });
    expect(dataSource.login).not.toHaveBeenCalled();
  });

  it('displays a clear inline error for wrong credentials (401)', async () => {
    vi.mocked(dataSource.login).mockRejectedValueOnce({
      response: {
        status: 401,
        data: { detail: 'No active account found with the given credentials' },
      },
    });

    render(
      <LoginPage
        onLoginSuccess={onLoginSuccess}
        onNavigateToRegister={onNavigateToRegister}
      />
    );

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'wrong_user' } });
    fireEvent.change(screen.getByPlaceholderText(/enter your password/i), {
      target: { value: 'bad_password' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in to platform/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/invalid username or password/i)).toBeInTheDocument();
    });
    expect(onLoginSuccess).not.toHaveBeenCalled();
  });

  it('displays a clear message when a server error occurs (500)', async () => {
    vi.mocked(dataSource.login).mockRejectedValueOnce({
      response: {
        status: 500,
        data: {},
      },
    });

    render(
      <LoginPage
        onLoginSuccess={onLoginSuccess}
        onNavigateToRegister={onNavigateToRegister}
      />
    );

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'demo_business' } });
    fireEvent.change(screen.getByPlaceholderText(/enter your password/i), {
      target: { value: 'password123' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in to platform/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(
        screen.getByText(/unable to connect to the authentication service/i)
      ).toBeInTheDocument();
    });
  });

  it('successfully logs in and invokes onLoginSuccess', async () => {
    const fakeUser = {
      id: 1,
      username: 'demo_business',
      organization: { id: 1, name: 'The Grand Gateway', type: 'BUSINESS' },
    };
    vi.mocked(dataSource.login).mockResolvedValueOnce({
      access: 'fake-access-token',
      refresh: 'fake-refresh-token',
      user: fakeUser as unknown as Parameters<typeof onLoginSuccess>[0],
    });

    render(
      <LoginPage
        onLoginSuccess={onLoginSuccess}
        onNavigateToRegister={onNavigateToRegister}
      />
    );

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'demo_business' } });
    fireEvent.change(screen.getByPlaceholderText(/enter your password/i), {
      target: { value: 'secret123' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in to platform/i }));

    await waitFor(() => {
      expect(dataSource.login).toHaveBeenCalledWith('demo_business', 'secret123', true);
      expect(onLoginSuccess).toHaveBeenCalledWith(fakeUser);
    });
  });
});

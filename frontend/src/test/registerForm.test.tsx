import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { RegisterPage } from '../pages/RegisterPage';
import { dataSource } from '../services';

vi.mock('../services', () => ({
  dataSource: {
    register: vi.fn(),
  },
}));

describe('RegisterForm Component', () => {
  const onRegisterSuccess = vi.fn();
  const onNavigateToLogin = vi.fn();
  const onBackToPlatform = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders registration form with selectable organization cards', () => {
    render(
      <RegisterPage
        onRegisterSuccess={onRegisterSuccess}
        onNavigateToLogin={onNavigateToLogin}
        onBackToPlatform={onBackToPlatform}
      />
    );

    expect(screen.getByText('Business / Donor')).toBeInTheDocument();
    expect(screen.getByText('NGO / Charity Partner')).toBeInTheDocument();
    expect(screen.getByLabelText(/organization name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/admin username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/work email/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/minimum 8 characters/i)).toBeInTheDocument();
  });

  it('toggles organization type and displays admin verification alert for NGOs', () => {
    render(
      <RegisterPage
        onRegisterSuccess={onRegisterSuccess}
        onNavigateToLogin={onNavigateToLogin}
        onBackToPlatform={onBackToPlatform}
      />
    );

    // Initial default: Business, no NGO verification warning
    expect(screen.queryByText(/Admin Verification Required:/i)).not.toBeInTheDocument();

    // Select NGO card
    const ngoCard = screen.getByText('NGO / Charity Partner').closest('button');
    expect(ngoCard).toBeInTheDocument();
    fireEvent.click(ngoCard!);

    // NGO verification note must now appear
    expect(screen.getByText(/Admin Verification Required:/i)).toBeInTheDocument();
  });

  it('enforces password rule (minimum 8 characters)', async () => {
    render(
      <RegisterPage
        onRegisterSuccess={onRegisterSuccess}
        onNavigateToLogin={onNavigateToLogin}
        onBackToPlatform={onBackToPlatform}
      />
    );

    fireEvent.change(screen.getByLabelText(/organization name/i), {
      target: { value: 'City Hunger Relief' },
    });
    fireEvent.change(screen.getByLabelText(/admin username/i), {
      target: { value: 'city_admin' },
    });
    fireEvent.change(screen.getByLabelText(/work email/i), {
      target: { value: 'admin@cityhunger.org' },
    });
    // Short password: only 6 chars
    fireEvent.change(screen.getByPlaceholderText(/minimum 8 characters/i), {
      target: { value: 'short6' },
    });

    const submitBtn = screen.getByRole('button', { name: /complete organization registration/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(
        screen.getByText(/password must be at least 8 characters/i)
      ).toBeInTheDocument();
    });
    expect(dataSource.register).not.toHaveBeenCalled();
  });

  it('successfully submits valid registration data', async () => {
    vi.mocked(dataSource.register).mockResolvedValueOnce({
      id: 10,
      username: 'city_admin',
      email: 'admin@cityhunger.org',
    } as unknown as Parameters<typeof onRegisterSuccess>[0]);

    render(
      <RegisterPage
        onRegisterSuccess={onRegisterSuccess}
        onNavigateToLogin={onNavigateToLogin}
        onBackToPlatform={onBackToPlatform}
      />
    );

    fireEvent.change(screen.getByLabelText(/organization name/i), {
      target: { value: 'City Hunger Relief' },
    });
    fireEvent.change(screen.getByLabelText(/admin username/i), {
      target: { value: 'city_admin' },
    });
    fireEvent.change(screen.getByLabelText(/work email/i), {
      target: { value: 'admin@cityhunger.org' },
    });
    fireEvent.change(screen.getByPlaceholderText(/minimum 8 characters/i), {
      target: { value: 'validPassword123' },
    });

    fireEvent.click(
      screen.getByRole('button', { name: /complete organization registration/i })
    );

    await waitFor(() => {
      expect(dataSource.register).toHaveBeenCalledWith({
        org_type: 'BUSINESS',
        org_name: 'City Hunger Relief',
        username: 'city_admin',
        email: 'admin@cityhunger.org',
        password: 'validPassword123',
        address: '',
        phone: '',
      });
      expect(onRegisterSuccess).toHaveBeenCalled();
    });
  });
});

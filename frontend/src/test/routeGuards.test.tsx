import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ForbiddenPage } from '../pages/ForbiddenPage';
import { PendingVerificationPage } from '../pages/PendingVerificationPage';
import { NotFoundPage } from '../pages/NotFoundPage';

describe('Route Guards & Access Control', () => {
  it('renders ForbiddenPage (403) when an NGO attempts to access a business-only route', () => {
    const handleGoHome = vi.fn();
    render(<ForbiddenPage onGoHome={handleGoHome} requiredRole="Business Organizations" />);

    expect(screen.getByText('403 Access Denied')).toBeInTheDocument();
    expect(screen.getByText('Restricted Area')).toBeInTheDocument();
    expect(screen.getByText(/reserved for Business Organizations/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /return to dashboard/i })).toBeInTheDocument();
  });

  it('renders PendingVerificationPage when an NGO organization is unverified', () => {
    const handleLogout = vi.fn();
    const handleSwitch = vi.fn();
    render(
      <PendingVerificationPage
        organizationName="Robin Hood Army Mysore"
        onLogout={handleLogout}
        onSwitchToBusinessDemo={handleSwitch}
      />
    );

    expect(screen.getByText('Verification in Progress')).toBeInTheDocument();
    expect(screen.getByText('Account Pending Administrator Approval')).toBeInTheDocument();
    expect(screen.getByText('Robin Hood Army Mysore')).toBeInTheDocument();
  });

  it('renders NotFoundPage (404) when an invalid route path is requested', () => {
    const handleGoHome = vi.fn();
    render(<NotFoundPage onGoHome={handleGoHome} />);

    expect(screen.getByText('404 Not Found')).toBeInTheDocument();
    expect(screen.getByText('Page Does Not Exist')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /back to dashboard/i })).toBeInTheDocument();
  });

  it('evaluates business-only route restrictions correctly', () => {
    const isBusinessOnlyRoute = (path: string) =>
      ['inventory', 'scan', 'import', 'donations'].includes(path);

    expect(isBusinessOnlyRoute('inventory')).toBe(true);
    expect(isBusinessOnlyRoute('scan')).toBe(true);
    expect(isBusinessOnlyRoute('import')).toBe(true);
    expect(isBusinessOnlyRoute('donations')).toBe(true);

    expect(isBusinessOnlyRoute('dashboard')).toBe(false);
    expect(isBusinessOnlyRoute('feed')).toBe(false);
    expect(isBusinessOnlyRoute('claims')).toBe(false);
    expect(isBusinessOnlyRoute('impact')).toBe(false);
    expect(isBusinessOnlyRoute('settings')).toBe(false);
  });
});

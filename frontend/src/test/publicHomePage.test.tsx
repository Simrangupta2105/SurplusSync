import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PublicHomePage } from '../pages/PublicHomePage';
import * as useDataModule from '../hooks/useData';

describe('Public Home Page at "/" (Task B2)', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
  });

  const renderComponent = (props: Partial<React.ComponentProps<typeof PublicHomePage>> = {}) => {
    const defaultProps = {
      onNavigateToLogin: vi.fn(),
      onNavigateToRegister: vi.fn(),
      isDark: true,
      onToggleDark: vi.fn(),
      isDemo: false,
    };
    return {
      ...render(
        <QueryClientProvider client={queryClient}>
          <PublicHomePage {...defaultProps} {...props} />
        </QueryClientProvider>
      ),
      props: { ...defaultProps, ...props },
    };
  };

  it('renders the navigation bar, logo, and single semantic h1 headline', () => {
    renderComponent();

    // Logo & Title
    expect(screen.getAllByText('SurplusSync').length).toBeGreaterThan(0);

    // Single semantic h1
    const headings = screen.getAllByRole('heading', { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent(/turning surplus food into real meals/i);

    // Subtext
    expect(
      screen.getByText(/a unified logistics platform connecting food businesses with verified ngos/i)
    ).toBeInTheDocument();
  });

  it('renders all three steps in the How It Works section', () => {
    renderComponent();

    expect(screen.getByText('How SurplusSync Works')).toBeInTheDocument();
    expect(screen.getByText('Track Inventory')).toBeInTheDocument();
    expect(screen.getByText('Identify Surplus')).toBeInTheDocument();
    expect(screen.getByText('Redistribute Food')).toBeInTheDocument();
  });

  it('renders For Businesses and For NGOs cards with actionable CTAs', () => {
    const onNavigateToRegister = vi.fn();
    renderComponent({ onNavigateToRegister });

    expect(screen.getByText(/for food businesses/i)).toBeInTheDocument();
    expect(screen.getByText(/for verified non-profits/i)).toBeInTheDocument();

    expect(screen.getByText(/reduce waste & automate surplus redistribution/i)).toBeInTheDocument();
    expect(screen.getByText(/reliable food rescue for community kitchens/i)).toBeInTheDocument();

    const bizButtons = screen.getAllByRole('button', { name: /register your business/i });
    expect(bizButtons.length).toBeGreaterThan(0);
    fireEvent.click(bizButtons[0]);
    expect(onNavigateToRegister).toHaveBeenCalledWith('BUSINESS');

    const ngoButtons = screen.getAllByRole('button', { name: /register as an ngo/i });
    expect(ngoButtons.length).toBeGreaterThan(0);
    fireEvent.click(ngoButtons[0]);
    expect(onNavigateToRegister).toHaveBeenCalledWith('NGO');
  });

  it('renders features grid and explicitly marks unreleased features as Coming Soon', () => {
    renderComponent();

    expect(screen.getByText('Enterprise Logistics Features')).toBeInTheDocument();
    expect(screen.getByText('Expiry Alerts')).toBeInTheDocument();
    expect(screen.getByText('Barcode Scanning')).toBeInTheDocument();
    expect(screen.getByText('CSV & POS Integration')).toBeInTheDocument();
    expect(screen.getByText('Automated Matching')).toBeInTheDocument();
    expect(screen.getByText('Pickup Scheduling')).toBeInTheDocument();
    expect(screen.getByText('Impact Tracking')).toBeInTheDocument();

    // AI Waste Prediction marked as Live ML
    expect(screen.getByText(/AI Waste Prediction/i)).toBeInTheDocument();
    expect(screen.getByText('Live ML')).toBeInTheDocument();
  });

  it('displays impact counters when public totals exist, with Sample data label in demo mode', async () => {
    vi.spyOn(useDataModule, 'usePublicHomeTotals').mockReturnValue({
      data: {
        kg_redistributed: 1420.5,
        meals: 3409,
        co2e: 3551.25,
        verified_donors: 12,
        verified_ngos: 8,
        completed_donations: 45,
      },
      isLoading: false,
    } as unknown as ReturnType<typeof useDataModule.usePublicHomeTotals>);

    renderComponent({ isDemo: true });

    const metricsSection = screen.getByLabelText(/platform impact metrics/i);
    expect(metricsSection).toBeInTheDocument();
    expect(screen.getByText('Sample data')).toBeInTheDocument();

    expect(within(metricsSection).getByText(/food diverted/i)).toBeInTheDocument();
    expect(within(metricsSection).getByText(/meals provided/i)).toBeInTheDocument();
    expect(within(metricsSection).getByText(/co₂e prevented/i)).toBeInTheDocument();
    expect(within(metricsSection).getByText(/verified donors/i)).toBeInTheDocument();
    expect(within(metricsSection).getByText(/verified ngos/i)).toBeInTheDocument();
    expect(within(metricsSection).getByText(/completed rescues/i)).toBeInTheDocument();
  });

  it('completely hides the impact counters strip when all totals are zero', () => {
    vi.spyOn(useDataModule, 'usePublicHomeTotals').mockReturnValue({
      data: {
        kg_redistributed: 0,
        meals: 0,
        co2e: 0,
        verified_donors: 0,
        verified_ngos: 0,
        completed_donations: 0,
      },
      isLoading: false,
    } as unknown as ReturnType<typeof useDataModule.usePublicHomeTotals>);

    renderComponent();

    expect(screen.queryByText(/verified platform impact/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/platform impact metrics/i)).not.toBeInTheDocument();
  });

  it('provides a keyboard-accessible FAQ accordion', () => {
    renderComponent();

    const faqButton = screen.getByRole('button', { name: /who can join surplusSync\?/i });
    expect(faqButton).toBeInTheDocument();
    expect(faqButton).toHaveAttribute('aria-expanded', 'false');

    // Toggle open with click
    fireEvent.click(faqButton);
    expect(faqButton).toHaveAttribute('aria-expanded', 'true');
    expect(
      screen.getByText(/surplusSync is designed for licensed commercial food businesses/i)
    ).toBeInTheDocument();

    // Toggle closed
    fireEvent.click(faqButton);
    expect(faqButton).toHaveAttribute('aria-expanded', 'false');
    expect(
      screen.queryByText(/surplusSync is designed for licensed commercial food businesses/i)
    ).not.toBeInTheDocument();
  });

  it('navigates to sign in when Sign In button is clicked', () => {
    const onNavigateToLogin = vi.fn();
    renderComponent({ onNavigateToLogin });

    const signInBtns = screen.getAllByRole('button', { name: /sign in/i });
    fireEvent.click(signInBtns[0]);
    expect(onNavigateToLogin).toHaveBeenCalled();
  });

  it('renders footer with dynamic copyright year and environment contact email', () => {
    renderComponent();

    const currentYear = new Date().getFullYear().toString();
    expect(screen.getByText(new RegExp(currentYear))).toBeInTheDocument();
    expect(screen.getByText(/support@surplussync\.org/i)).toBeInTheDocument();
    expect(screen.getByText(/multi-tenant database isolation & honest zero-data reporting/i)).toBeInTheDocument();
  });
});

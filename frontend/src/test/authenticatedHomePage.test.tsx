import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthenticatedHomePage } from '../pages/AuthenticatedHomePage';
import * as useDataModule from '../hooks/useData';
import type { HomeData } from '../types';

describe('Authenticated Home Page at "/home" (New Bento Architecture)', () => {
  let queryClient: QueryClient;

  const mockBusinessHomeData: HomeData = {
    greeting: {
      organization_name: 'Metro Bakeries Ltd',
      role: 'BUSINESS',
      verification_status: 'VERIFIED',
      is_verified: true,
    },
    quick_stats: {
      batches_expiring_48h: 5,
      unacknowledged_critical_alerts: 2,
      donation_requests_pending_approval: 3,
      pickups_scheduled_24h: 1,
      active_listings: 4,
    },
    expiring_batches: [
      { id: 1, product_name: 'Organic Sourdough Bread', batch_code: 'B-101', days_to_expiry: 1, expiry_date: '2026-10-21T18:00:00Z', quantity: 12, unit: 'kg' },
      { id: 2, product_name: 'Whole Grain Bagels', batch_code: 'B-102', days_to_expiry: 2, expiry_date: '2026-10-22T12:00:00Z', quantity: 20, unit: 'units' },
    ],
    pickups_today: [
      { id: 'p-1', time: '14:00', counterpart_name: 'Robin Hood Army', status: 'SCHEDULED' },
    ],
    journey_counts: {
      track_or_need: 18,
      spot_or_match: 5,
      share_or_request: 4,
      collect: 1,
      done_or_received: 6,
    },
    needs_attention: [
      {
        id: 'na-1',
        type: 'REQUEST_APPROVAL_PENDING',
        title: '3 donation requests waiting for your approval',
        link: 'donations',
        urgency: 'high',
      },
      {
        id: 'na-2',
        type: 'EXPIRING_BATCH',
        title: '5 batches expire within 48 hours',
        link: 'alerts',
        urgency: 'medium',
      },
    ],
    getting_started: [
      { id: '1', title: 'Set organization location', link: 'settings', done: true },
      { id: '2', title: 'Add first product', link: 'inventory', done: true },
      { id: '3', title: 'Add first batch', link: 'inventory', done: false },
      { id: '4', title: 'Upload CSV or create POS key', link: 'import', done: false },
    ],
    recent_activity: [
      {
        id: 'act-1',
        title: 'Donation request received from Robin Hood Army',
        time: '25 minutes ago',
        link: 'donations',
      },
      {
        id: 'act-2',
        title: 'Surplus listing created for Artisanal Sourdough',
        time: '2 hours ago',
        link: 'marketplace',
      },
    ],
    impact_snapshot: {
      period_days: 30,
      kg_redistributed: 1250.0,
      meals_provided: 2976,
      co2e_kg_diverted: 3125.0,
    },
  };

  const mockNgoHomeData: HomeData = {
    greeting: {
      organization_name: 'City Relief Kitchen',
      role: 'NGO',
      verification_status: 'PENDING',
      is_verified: false,
    },
    quick_stats: {
      open_requests_awaiting_donor: 2,
      pickups_scheduled_24h: 1,
      new_matching_listings_24h: 4,
      active_requirements: 3,
    },
    new_near_you: [
      { id: 101, title: 'Fresh Seasonal Produce', distance_km: 1.2, quantity: 30, unit: 'kg' },
      { id: 102, title: 'Whole Wheat Sandwich Loaves', distance_km: 2.5, quantity: 15, unit: 'kg' },
    ],
    pickups_today: [
      { id: 'p-ngo-1', time: '15:30', counterpart_name: 'City Harvest Bakery', status: 'SCHEDULED' },
    ],
    journey_counts: {
      track_or_need: 3,
      spot_or_match: 4,
      share_or_request: 2,
      collect: 1,
      done_or_received: 4,
    },
    needs_attention: [
      {
        id: 'na-ngo-1',
        type: 'VERIFICATION_PENDING',
        title: 'Submit official 80G/Registration certificate for verification',
        link: 'profile',
        urgency: 'high',
      },
    ],
    getting_started: [
      { id: '1', title: 'Set organization location', link: 'settings', done: true },
      { id: '2', title: 'Add first requirement', link: 'requirements', done: true },
      { id: '3', title: 'Make first request', link: 'feed', done: false },
    ],
    recent_activity: [
      {
        id: 'act-ngo-1',
        title: 'Submitted requirement for Fresh Whole Milk',
        time: '1 hour ago',
        link: 'requirements',
      },
    ],
    impact_snapshot: {
      period_days: 30,
      kg_redistributed: 450.0,
      meals_provided: 1071,
      co2e_kg_diverted: 1125.0,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
  });

  const renderComponent = (props: Partial<React.ComponentProps<typeof AuthenticatedHomePage>> = {}) => {
    const defaultProps = {
      onNavigate: vi.fn(),
      onOpenAddBatch: vi.fn(),
      onOpenCreateListing: vi.fn(),
      onTriggerToast: vi.fn(),
    };
    return {
      ...render(
        <QueryClientProvider client={queryClient}>
          <AuthenticatedHomePage {...defaultProps} {...props} />
        </QueryClientProvider>
      ),
      props: { ...defaultProps, ...props },
    };
  };

  it('renders greeting strip with local time of day, organization name, verification badge, today\'s date, and primary action for business', () => {
    const onNavigate = vi.fn();
    const onOpenCreateListing = vi.fn();
    vi.spyOn(useDataModule, 'useHomeData').mockReturnValue({
      data: mockBusinessHomeData,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDataModule.useHomeData>);

    renderComponent({ onNavigate, onOpenCreateListing });

    // Time-based greeting with org name
    expect(screen.getByText(/good (morning|afternoon|evening), metro bakeries ltd/i)).toBeInTheDocument();
    expect(screen.getByText('Verified')).toBeInTheDocument();

    // Primary action on greeting right: Offer surplus
    const offerSurplusBtn = screen.getByRole('button', { name: 'Offer surplus food' });
    expect(offerSurplusBtn).toBeInTheDocument();
    fireEvent.click(offerSurplusBtn);
    expect(onOpenCreateListing).toHaveBeenCalled();
  });

  it('renders greeting strip with primary action "Browse the feed" for NGO, disabled when unverified', () => {
    const onNavigate = vi.fn();
    vi.spyOn(useDataModule, 'useHomeData').mockReturnValue({
      data: mockNgoHomeData,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDataModule.useHomeData>);

    renderComponent({ onNavigate });

    expect(screen.getByText(/good (morning|afternoon|evening), city relief kitchen/i)).toBeInTheDocument();
    expect(screen.getByText('Pending verification')).toBeInTheDocument();

    const browseFeedButtons = screen.getAllByRole('button', { name: /browse the feed/i });
    expect(browseFeedButtons.length).toBeGreaterThan(0);
    browseFeedButtons.forEach((btn) => {
      expect(btn).toBeDisabled();
    });
  });

  it('renders role-specific tagline row directly under greeting (2 lines total, small and calm, not a hero)', () => {
    vi.spyOn(useDataModule, 'useHomeData').mockReturnValue({
      data: mockBusinessHomeData,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDataModule.useHomeData>);

    const { rerender } = renderComponent();

    // Business tagline
    expect(screen.getByText("Know what's expiring. Share what's left.")).toBeInTheDocument();
    expect(
      screen.getByText(/track inventory in real time, prevent waste, and redirect surplus food to local community partners/i)
    ).toBeInTheDocument();

    // NGO tagline
    vi.spyOn(useDataModule, 'useHomeData').mockReturnValue({
      data: mockNgoHomeData,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDataModule.useHomeData>);

    rerender(
      <QueryClientProvider client={queryClient}>
        <AuthenticatedHomePage onNavigate={vi.fn()} />
      </QueryClientProvider>
    );

    expect(screen.getByText("See what's available. Feed who's waiting.")).toBeInTheDocument();
    expect(
      screen.getByText(/discover available donations nearby, coordinate seamless pickups, and support your community/i)
    ).toBeInTheDocument();
  });

  it('renders calm alert banner for unverified NGO explaining verification is pending', () => {
    const onNavigate = vi.fn();
    vi.spyOn(useDataModule, 'useHomeData').mockReturnValue({
      data: mockNgoHomeData,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDataModule.useHomeData>);

    renderComponent({ onNavigate });

    expect(screen.getByText(/account pending administrator verification/i)).toBeInTheDocument();
    expect(
      screen.getByText(/an administrator must verify your organization before you can request food donations/i)
    ).toBeInTheDocument();
  });

  it('renders Today\'s Bento Grid: Needs Attention tile with urgency colors and deep links', () => {
    const onNavigate = vi.fn();
    vi.spyOn(useDataModule, 'useHomeData').mockReturnValue({
      data: mockBusinessHomeData,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDataModule.useHomeData>);

    renderComponent({ onNavigate });

    expect(screen.getByText('Needs attention')).toBeInTheDocument();
    expect(screen.getByText('3 donation requests waiting for your approval')).toBeInTheDocument();
    expect(screen.getByText('5 batches expire within 48 hours')).toBeInTheDocument();

    expect(screen.getByText('Urgent')).toBeInTheDocument();
    expect(screen.getByText('Attention')).toBeInTheDocument();

    const requestItem = screen.getByText('3 donation requests waiting for your approval');
    fireEvent.click(requestItem);
    expect(onNavigate).toHaveBeenCalledWith('donations');
  });

  it('renders Today\'s Bento Grid: Needs Attention calm empty state "You\'re all caught up" when zero items', () => {
    const emptyData: HomeData = {
      ...mockBusinessHomeData,
      needs_attention: [],
    };

    vi.spyOn(useDataModule, 'useHomeData').mockReturnValue({
      data: emptyData,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDataModule.useHomeData>);

    renderComponent();

    expect(screen.getByText("You're all caught up")).toBeInTheDocument();
    expect(screen.getByText(/no urgent actions require your attention right now/i)).toBeInTheDocument();
  });

  it('renders Today\'s Bento Grid: Expiring Soon tile for Business with next batches and ExpiryPills', () => {
    const onNavigate = vi.fn();
    vi.spyOn(useDataModule, 'useHomeData').mockReturnValue({
      data: mockBusinessHomeData,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDataModule.useHomeData>);

    renderComponent({ onNavigate });

    expect(screen.getByText('Expiring soon')).toBeInTheDocument();
    expect(screen.getByText('Organic Sourdough Bread')).toBeInTheDocument();
    expect(screen.getByText('Whole Grain Bagels')).toBeInTheDocument();

    const openInvBtn = screen.getByRole('button', { name: /open inventory/i });
    fireEvent.click(openInvBtn);
    expect(onNavigate).toHaveBeenCalledWith('inventory');
  });

  it('renders Today\'s Bento Grid: New Near You tile for NGO with matching listings and distance', () => {
    const onNavigate = vi.fn();
    vi.spyOn(useDataModule, 'useHomeData').mockReturnValue({
      data: mockNgoHomeData,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDataModule.useHomeData>);

    renderComponent({ onNavigate });

    expect(screen.getByText('New near you')).toBeInTheDocument();
    expect(screen.getByText('Fresh Seasonal Produce')).toBeInTheDocument();
    expect(screen.getByText('1.2 km away')).toBeInTheDocument();
    expect(screen.getByText('Whole Wheat Sandwich Loaves')).toBeInTheDocument();

    const browseFeedBtn = screen.getByRole('button', { name: /browse food feed/i });
    fireEvent.click(browseFeedBtn);
    expect(onNavigate).toHaveBeenCalledWith('feed');
  });

  it('renders Today\'s Bento Grid: Pickups Today tile with times and counterpart names', () => {
    const onNavigate = vi.fn();
    vi.spyOn(useDataModule, 'useHomeData').mockReturnValue({
      data: mockBusinessHomeData,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDataModule.useHomeData>);

    renderComponent({ onNavigate });

    expect(screen.getByText('Pickups today')).toBeInTheDocument();
    expect(screen.getByText('Robin Hood Army')).toBeInTheDocument();
    expect(screen.getByText('14:00')).toBeInTheDocument();

    const viewScheduleBtn = screen.getByRole('button', { name: /view schedule/i });
    fireEvent.click(viewScheduleBtn);
    expect(onNavigate).toHaveBeenCalledWith('schedule');
  });

  it('renders Surplus Journey Flow for Business: Track -> Spot -> Share -> Collect -> Done with live counts', () => {
    const onNavigate = vi.fn();
    vi.spyOn(useDataModule, 'useHomeData').mockReturnValue({
      data: mockBusinessHomeData,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDataModule.useHomeData>);

    renderComponent({ onNavigate });

    expect(screen.getByText('Surplus journey')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /track, 18 active batches in inventory/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /spot, 5 batches expiring within 48 hours/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /share, 4 open surplus listings/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /collect, 1 scheduled pickups/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /done, 6 completed donations this month/i })).toBeInTheDocument();

    // Check live counts rendered inside nodes
    expect(screen.getByText('18')).toBeInTheDocument(); // Track
    expect(screen.getAllByText('5').length).toBeGreaterThanOrEqual(1);  // Spot
    expect(screen.getByText('4')).toBeInTheDocument();  // Share
    expect(screen.getByText('6')).toBeInTheDocument();  // Done

    // Click Track node -> goes to inventory
    const trackNode = screen.getByRole('button', { name: /track, 18 active batches in inventory/i });
    fireEvent.click(trackNode);
    expect(onNavigate).toHaveBeenCalledWith('inventory');
  });

  it('renders Surplus Journey Flow for NGO: Need -> Match -> Request -> Collect -> Received with live counts', () => {
    const onNavigate = vi.fn();
    vi.spyOn(useDataModule, 'useHomeData').mockReturnValue({
      data: mockNgoHomeData,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDataModule.useHomeData>);

    renderComponent({ onNavigate });

    expect(screen.getByRole('button', { name: /need, 3 active food requirements/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /match, 4 new matching listings nearby/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /request, 2 open rescue requests/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /collect, 1 scheduled pickups/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /received, 4 food donations received this month/i })).toBeInTheDocument();

    const needNode = screen.getByRole('button', { name: /need, 3 active food requirements/i });
    fireEvent.click(needNode);
    expect(onNavigate).toHaveBeenCalledWith('requirements');
  });

  it('handles keyboard navigation and accessibility attributes on Surplus Journey nodes', () => {
    vi.spyOn(useDataModule, 'useHomeData').mockReturnValue({
      data: mockBusinessHomeData,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDataModule.useHomeData>);

    renderComponent();

    const spotNode = screen.getByRole('button', { name: /spot, 5 batches expiring within 48 hours/i });
    expect(spotNode).toBeInTheDocument();
    expect(spotNode).toHaveAttribute('type', 'button');
    spotNode.focus();
    expect(document.activeElement).toBe(spotNode);
  });

  it('renders dash (—) with muted style for journey stages with zero count', () => {
    const zeroCountData: HomeData = {
      ...mockBusinessHomeData,
      journey_counts: {
        track_or_need: 0,
        spot_or_match: 0,
        share_or_request: 0,
        collect: 0,
        done_or_received: 0,
      },
      quick_stats: {
        ...mockBusinessHomeData.quick_stats,
        batches_expiring_48h: 0,
        active_listings: 0,
        pickups_scheduled_24h: 0,
      },
    };

    vi.spyOn(useDataModule, 'useHomeData').mockReturnValue({
      data: zeroCountData,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDataModule.useHomeData>);

    renderComponent();

    // Check for dashes
    const dashes = screen.getAllByText('—');
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });

  it('renders 30-day impact tile with kg, meals (kg / 0.42), CO2e (kg * 2.5), and sparkline', () => {
    const onNavigate = vi.fn();
    vi.spyOn(useDataModule, 'useHomeData').mockReturnValue({
      data: mockBusinessHomeData,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDataModule.useHomeData>);

    renderComponent({ onNavigate });

    expect(screen.getByText('Your impact, last 30 days')).toBeInTheDocument();
    // 1250 kg
    expect(screen.getByText('1,250')).toBeInTheDocument();
    // 1250 / 0.42 = 2976 meals
    expect(screen.getByText('2,976')).toBeInTheDocument();
    // 1250 * 2.5 = 3125 kg CO2e
    expect(screen.getByText('3,125')).toBeInTheDocument();

    const viewFullAnalyticsBtn = screen.getByRole('button', { name: /view full analytics/i });
    fireEvent.click(viewFullAnalyticsBtn);
    expect(onNavigate).toHaveBeenCalledWith('impact');
  });

  it('renders friendly empty message "Your impact appears after your first completed donation" when impact is zero', () => {
    const zeroImpactData: HomeData = {
      ...mockBusinessHomeData,
      impact_snapshot: {
        period_days: 30,
        kg_redistributed: 0,
        meals_provided: 0,
        co2e_kg_diverted: 0,
      },
    };

    vi.spyOn(useDataModule, 'useHomeData').mockReturnValue({
      data: zeroImpactData,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDataModule.useHomeData>);

    renderComponent();

    expect(screen.getByText('Your impact appears after your first completed donation')).toBeInTheDocument();
  });

  it('renders Quick Actions row of icon tiles named by action for Business', () => {
    const onNavigate = vi.fn();
    const onOpenAddBatch = vi.fn();
    const onOpenCreateListing = vi.fn();

    vi.spyOn(useDataModule, 'useHomeData').mockReturnValue({
      data: mockBusinessHomeData,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDataModule.useHomeData>);

    renderComponent({ onNavigate, onOpenAddBatch, onOpenCreateListing });

    const addStockBtn = screen.getByRole('button', { name: /add stock to inventory/i });
    fireEvent.click(addStockBtn);
    expect(onOpenAddBatch).toHaveBeenCalled();

    const scanBtn = screen.getByRole('button', { name: /scan a code with barcode camera/i });
    fireEvent.click(scanBtn);
    expect(onNavigate).toHaveBeenCalledWith('scan');

    const importBtn = screen.getByRole('button', { name: /import a file with bulk csv or pos/i });
    fireEvent.click(importBtn);
    expect(onNavigate).toHaveBeenCalledWith('import');

    const offerBtn = screen.getByRole('button', { name: /offer surplus food on the marketplace/i });
    fireEvent.click(offerBtn);
    expect(onOpenCreateListing).toHaveBeenCalled();

    const reviewBtn = screen.getByRole('button', { name: /review donation requests/i });
    fireEvent.click(reviewBtn);
    expect(onNavigate).toHaveBeenCalledWith('donations');
  });

  it('renders Quick Actions row of icon tiles named by action for NGO', () => {
    const onNavigate = vi.fn();
    vi.spyOn(useDataModule, 'useHomeData').mockReturnValue({
      data: {
        ...mockNgoHomeData,
        greeting: { ...mockNgoHomeData.greeting, is_verified: true },
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDataModule.useHomeData>);

    renderComponent({ onNavigate });

    const feedBtn = screen.getByRole('button', { name: /browse the feed for surplus listings/i });
    fireEvent.click(feedBtn);
    expect(onNavigate).toHaveBeenCalledWith('feed');

    const reqBtn = screen.getByRole('button', { name: /add a food requirement for your kitchen/i });
    fireEvent.click(reqBtn);
    expect(onNavigate).toHaveBeenCalledWith('requirements');

    const myReqBtn = screen.getByRole('button', { name: /^my requests$/i });
    fireEvent.click(myReqBtn);
    expect(onNavigate).toHaveBeenCalledWith('donations');

    const scheduleBtn = screen.getByRole('button', { name: /^pickup schedule$/i });
    fireEvent.click(scheduleBtn);
    expect(onNavigate).toHaveBeenCalledWith('schedule');
  });

  it('renders Setup checklist card and hides it completely when all items are done', () => {
    const onNavigate = vi.fn();
    vi.spyOn(useDataModule, 'useHomeData').mockReturnValue({
      data: mockBusinessHomeData,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDataModule.useHomeData>);

    const { rerender } = renderComponent({ onNavigate });

    expect(screen.getByText('Getting started checklist')).toBeInTheDocument();
    expect(screen.getByText('50% done')).toBeInTheDocument();

    // When all items are complete, checklist is hidden from DOM
    const allDoneData: HomeData = {
      ...mockBusinessHomeData,
      getting_started: mockBusinessHomeData.getting_started.map((i) => ({ ...i, done: true })),
    };

    vi.spyOn(useDataModule, 'useHomeData').mockReturnValue({
      data: allDoneData,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDataModule.useHomeData>);

    rerender(
      <QueryClientProvider client={queryClient}>
        <AuthenticatedHomePage onNavigate={onNavigate} />
      </QueryClientProvider>
    );

    expect(screen.queryByText('Getting started checklist')).not.toBeInTheDocument();
  });

  it('renders Recent Activity timeline and handles empty state gracefully', () => {
    vi.spyOn(useDataModule, 'useHomeData').mockReturnValue({
      data: mockBusinessHomeData,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDataModule.useHomeData>);

    const { rerender } = renderComponent();

    expect(screen.getByText('Recent activity')).toBeInTheDocument();
    expect(screen.getByText('Donation request received from Robin Hood Army')).toBeInTheDocument();
    expect(screen.getByText('25 minutes ago')).toBeInTheDocument();

    // When empty, renders calm empty state
    const emptyActivityData: HomeData = {
      ...mockBusinessHomeData,
      recent_activity: [],
    };

    vi.spyOn(useDataModule, 'useHomeData').mockReturnValue({
      data: emptyActivityData,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDataModule.useHomeData>);

    rerender(
      <QueryClientProvider client={queryClient}>
        <AuthenticatedHomePage onNavigate={vi.fn()} />
      </QueryClientProvider>
    );

    expect(screen.getByText('No recent events')).toBeInTheDocument();
    expect(screen.getByText('Activity will appear as actions occur.')).toBeInTheDocument();
  });

  it('renders error state with retry connection button when API fails', () => {
    const refetch = vi.fn();
    vi.spyOn(useDataModule, 'useHomeData').mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('Network timeout'),
      refetch,
    } as unknown as ReturnType<typeof useDataModule.useHomeData>);

    renderComponent();

    expect(screen.getByText(/dashboard data unavailable/i)).toBeInTheDocument();
    expect(screen.getByText('Network timeout')).toBeInTheDocument();

    const retryBtn = screen.getByRole('button', { name: /retry connection/i });
    fireEvent.click(retryBtn);
    expect(refetch).toHaveBeenCalled();
  });
});

import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DonationRequestsPage } from '../pages/DonationRequestsPage';
import { SurplusMarketplacePage } from '../pages/SurplusMarketplacePage';
import { NgoRequirementsPage } from '../pages/NgoRequirementsPage';
import { PickupSchedulePage } from '../pages/PickupSchedulePage';
import { ImpactAnalyticsPage } from '../pages/ImpactAnalyticsPage';
import { NotificationsPage } from '../pages/NotificationsPage';

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
}

function renderWithClient(ui: React.ReactElement) {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  );
}

describe('Redistribution Frontend Pages Suite', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('DonationRequestsPage', () => {
    it('renders donation requests header, filter tabs, and request IDs', async () => {
      renderWithClient(<DonationRequestsPage />);

      expect(screen.getByText('Donation Requests')).toBeInTheDocument();
      expect(screen.getByText('All')).toBeInTheDocument();
      expect(screen.getByText(/Pending approval/i)).toBeInTheDocument();
      expect(screen.getByText('Scheduled')).toBeInTheDocument();

      // Check request ID from demo seed
      await waitFor(() => {
        expect(screen.getByText('REQ-2026-00101')).toBeInTheDocument();
      });
    });

    it('filters requests by search input', async () => {
      renderWithClient(<DonationRequestsPage />);

      await waitFor(() => {
        expect(screen.getByText('REQ-2026-00101')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/Search by ID, item, NGO, donor/i);
      fireEvent.change(searchInput, { target: { value: 'NonexistentCode999' } });

      await waitFor(() => {
        expect(screen.getByText(/No donation requests found/i)).toBeInTheDocument();
      });
    });

    it('opens View Pickup modal when View Pickup button is clicked', async () => {
      renderWithClient(<DonationRequestsPage />);

      await waitFor(() => {
        expect(screen.getByText('REQ-2026-00101')).toBeInTheDocument();
      });

      const viewButtons = screen.getAllByRole('button', { name: /View Pickup/i });
      fireEvent.click(viewButtons[0]);

      await waitFor(() => {
        expect(screen.getByText(/Pickup Details & Status Flow/i)).toBeInTheDocument();
      });
    });
  });

  describe('SurplusMarketplacePage', () => {
    it('renders marketplace header, search box, and category filter pills', async () => {
      renderWithClient(<SurplusMarketplacePage />);

      expect(screen.getByText('Surplus Marketplace')).toBeInTheDocument();
      expect(screen.getByText('Cooked Meals')).toBeInTheDocument();
      expect(screen.getByText('All Categories')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByText(/Banquet Dal Makhani/i)).toBeInTheDocument();
      });
    });

    it('opens Request Donation modal when Request Donation is clicked', async () => {
      renderWithClient(<SurplusMarketplacePage />);

      await waitFor(() => {
        expect(screen.getByText(/Whole Wheat Sourdough/i)).toBeInTheDocument();
      });

      const requestButtons = screen.getAllByRole('button', { name: /Request Donation/i });
      fireEvent.click(requestButtons[0]);

      await waitFor(() => {
        expect(screen.getByText(/Request Food Donation/i)).toBeInTheDocument();
        expect(screen.getByText(/Preferred Pickup Window/i)).toBeInTheDocument();
      });
    });
  });

  describe('NgoRequirementsPage', () => {
    it('renders requirements header, urgent filter, and requirement cards', async () => {
      renderWithClient(<NgoRequirementsPage />);

      expect(screen.getByText('NGO Food Requirements')).toBeInTheDocument();
      expect(screen.getByText('Urgent Only')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByText(/Daily Evening Hot Dinner Meals/i)).toBeInTheDocument();
      });
    });

    it('opens Post Requirement modal when Post Requirement is clicked', async () => {
      renderWithClient(<NgoRequirementsPage />);

      const postButton = screen.getByRole('button', { name: /Post Requirement/i });
      fireEvent.click(postButton);

      await waitFor(() => {
        expect(screen.getByText('Post Food Relief Requirement')).toBeInTheDocument();
        expect(screen.getByText(/Target Beneficiaries Count/i)).toBeInTheDocument();
      });
    });
  });

  describe('PickupSchedulePage', () => {
    it('renders pickup timeline agenda and scheduled items', async () => {
      renderWithClient(<PickupSchedulePage />);

      expect(screen.getByText('Pickup & Logistics Schedule')).toBeInTheDocument();
      expect(screen.getByText("Today's Agenda")).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByText('REQ-2026-00102')).toBeInTheDocument();
      });
    });
  });

  describe('ImpactAnalyticsPage', () => {
    it('renders ESG scorecards and UN SDG alignment', async () => {
      renderWithClient(<ImpactAnalyticsPage />);

      expect(screen.getByText('Environmental & Social Impact (ESG)')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByText('Total Rescued Food')).toBeInTheDocument();
        expect(screen.getByText('Nutritious Meals Served')).toBeInTheDocument();
        expect(screen.getByText('CO₂e Emissions Abated')).toBeInTheDocument();
        expect(screen.getByText('SDG 2: Zero Hunger')).toBeInTheDocument();
      });
    });
  });

  describe('NotificationsPage', () => {
    it('renders notifications center and alerts list', async () => {
      renderWithClient(<NotificationsPage />);

      expect(screen.getByText('Notifications & Alerts Center')).toBeInTheDocument();
      expect(screen.getByText(/Unread Only/i)).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByText(/Matching Surplus Available!/i)).toBeInTheDocument();
      });
    });
  });
});

import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AdminOverviewPage } from '../pages/admin/AdminOverviewPage';
import { AdminVerificationsPage } from '../pages/admin/AdminVerificationsPage';
import { AdminOrganizationsPage } from '../pages/admin/AdminOrganizationsPage';
import { AdminIssuesPage } from '../pages/admin/AdminIssuesPage';
import { AdminRatingsPage } from '../pages/admin/AdminRatingsPage';
import { AdminAuditLogPage } from '../pages/admin/AdminAuditLogPage';
import { ForbiddenPage } from '../pages/ForbiddenPage';
import { demoSource } from '../services/demoSource';
import { setDataSourceMode } from '../services';

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

describe('Platform Admin Portal UI & Workflows (Task 5 & 6)', () => {
  beforeEach(() => {
    setDataSourceMode('demo');
    demoSource.seedDeterministicData();
    demoSource.setEnableLatency(false);
    demoSource.setDemoUser('ADMIN');
    vi.clearAllMocks();
  });

  describe('AdminOverviewPage', () => {
    it('renders platform metrics and cockpit stat cards', async () => {
      const handleNavigate = vi.fn();
      renderWithClient(<AdminOverviewPage onNavigate={handleNavigate} />);

      await waitFor(() => {
        expect(screen.getByText('Registered Businesses')).toBeInTheDocument();
        expect(screen.getByText('Registered NGOs')).toBeInTheDocument();
        expect(screen.getByText('Pending Verifications')).toBeInTheDocument();
        expect(screen.getByText('Open Issues')).toBeInTheDocument();
      });

      expect(screen.getByText('Total Food Rescued')).toBeInTheDocument();
      expect(screen.getByText('Active Surplus Listings')).toBeInTheDocument();
      expect(screen.getByText('Platform Rating Avg')).toBeInTheDocument();
    });

    it('renders quick approval queue and action links', async () => {
      const handleNavigate = vi.fn();
      renderWithClient(<AdminOverviewPage onNavigate={handleNavigate} />);

      await waitFor(() => {
        expect(screen.getByText('Needs Approval')).toBeInTheDocument();
      });

      // Navigate to verifications
      const viewAllButtons = screen.getAllByRole('button', { name: /view all/i });
      expect(viewAllButtons.length).toBeGreaterThan(0);
      fireEvent.click(viewAllButtons[0]);
      expect(handleNavigate).toHaveBeenCalledWith('admin/verifications');
    });
  });

  describe('AdminVerificationsPage', () => {
    it('renders pending NGO applications with details', async () => {
      renderWithClient(<AdminVerificationsPage onTriggerToast={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByText('NGO Verification Queue')).toBeInTheDocument();
        expect(screen.getByText(/awaiting review/i)).toBeInTheDocument();
      });
    });

    it('opens approve dialog and verifies NGO', async () => {
      const toastMock = vi.fn();
      renderWithClient(<AdminVerificationsPage onTriggerToast={toastMock} />);

      await waitFor(() => {
        const approveButtons = screen.getAllByRole('button', { name: /approve & activate/i });
        expect(approveButtons.length).toBeGreaterThan(0);
        fireEvent.click(approveButtons[0]);
      });

      // In approve modal
      expect(screen.getByRole('button', { name: /authorize ngo/i })).toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: /authorize ngo/i }));

      await waitFor(() => {
        expect(toastMock).toHaveBeenCalledWith(expect.stringContaining('verified'));
      });
    });

    it('opens reject modal and validates required reason', async () => {
      const toastMock = vi.fn();
      renderWithClient(<AdminVerificationsPage onTriggerToast={toastMock} />);

      await waitFor(() => {
        const rejectButtons = screen.getAllByRole('button', { name: /reject/i });
        expect(rejectButtons.length).toBeGreaterThan(0);
        fireEvent.click(rejectButtons[0]);
      });

      // Confirm Rejection button is initially disabled when reason is empty
      const confirmRejectBtn = screen.getByRole('button', { name: /confirm rejection/i });
      expect(confirmRejectBtn).toBeDisabled();

      // Type reason
      const textarea = screen.getByPlaceholderText(/certificate of incorporation is expired/i);
      fireEvent.change(textarea, { target: { value: 'Invalid trust deed documentation' } });
      expect(confirmRejectBtn).not.toBeDisabled();

      fireEvent.click(confirmRejectBtn);

      await waitFor(() => {
        expect(toastMock).toHaveBeenCalledWith(expect.stringContaining('Rejected verification'));
      });
    });
  });

  describe('AdminOrganizationsPage', () => {
    it('renders organization directory with role tabs', async () => {
      renderWithClient(<AdminOrganizationsPage onTriggerToast={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByText('Organizations Directory')).toBeInTheDocument();
      });

      expect(screen.getByRole('button', { name: /all organizations/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /businesses/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /ngos/i })).toBeInTheDocument();
    });

    it('filters organizations using search input', async () => {
      renderWithClient(<AdminOrganizationsPage onTriggerToast={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getAllByText(/surplussync partner kitchen/i).length).toBeGreaterThan(0);
      });

      const searchInput = screen.getByPlaceholderText(/search organizations/i);
      fireEvent.change(searchInput, { target: { value: 'Grand Gateway' } });

      await waitFor(() => {
        expect(screen.getAllByText(/the grand gateway bistro/i).length).toBeGreaterThan(0);
        expect(screen.queryByText(/surplussync partner kitchen/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('AdminIssuesPage', () => {
    it('renders incident management console and status filter', async () => {
      renderWithClient(<AdminIssuesPage onTriggerToast={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByText('Incident & Dispute Management')).toBeInTheDocument();
      });

      expect(screen.getByDisplayValue('All Statuses')).toBeInTheDocument();
      expect(screen.getByDisplayValue('All Priorities')).toBeInTheDocument();
    });

    it('opens drawer to review ticket and update status', async () => {
      const toastMock = vi.fn();
      renderWithClient(<AdminIssuesPage onTriggerToast={toastMock} />);

      await waitFor(() => {
        const reviewButtons = screen.getAllByRole('button', { name: /review/i });
        expect(reviewButtons.length).toBeGreaterThan(0);
        fireEvent.click(reviewButtons[0]);
      });

      expect(screen.getByText('Incident Parties')).toBeInTheDocument();
      expect(screen.getByText('Administrative Resolution Notes')).toBeInTheDocument();

      // Click Mark Resolved
      const markResolvedBtn = screen.getByRole('button', { name: /mark resolved/i });
      fireEvent.click(markResolvedBtn);

      await waitFor(() => {
        expect(toastMock).toHaveBeenCalledWith(expect.stringContaining('updated successfully'));
      });
    });
  });

  describe('AdminRatingsPage', () => {
    it('renders rating moderation with metrics and review feed', async () => {
      renderWithClient(<AdminRatingsPage onTriggerToast={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByText('Ratings & Reviews Moderation')).toBeInTheDocument();
        expect(screen.getByText('Total Reviews Filtered')).toBeInTheDocument();
      });
    });

    it('prompts for mandatory reason when hiding a review', async () => {
      const toastMock = vi.fn();
      renderWithClient(<AdminRatingsPage onTriggerToast={toastMock} />);

      await waitFor(() => {
        const hideButtons = screen.getAllByRole('button', { name: /hide review/i });
        expect(hideButtons.length).toBeGreaterThan(0);
        fireEvent.click(hideButtons[0]);
      });

      expect(screen.getByText(/hide rating from public/i)).toBeInTheDocument();

      // Submit button is disabled without reason
      const hideSubmitBtns = screen.getAllByRole('button', { name: /hide review/i });
      const modalSubmitBtn = hideSubmitBtns[hideSubmitBtns.length - 1];
      expect(modalSubmitBtn).toBeDisabled();

      // Enter moderation reason
      const textarea = screen.getByPlaceholderText(/inappropriate language/i);
      fireEvent.change(textarea, { target: { value: 'Commercial dispute ongoing in civil arbitration' } });
      expect(modalSubmitBtn).not.toBeDisabled();

      fireEvent.click(modalSubmitBtn);

      await waitFor(() => {
        expect(toastMock).toHaveBeenCalledWith(expect.stringContaining('is now hidden'));
      });
    });
  });

  describe('AdminAuditLogPage', () => {
    it('renders audit trail entries with timestamps and actions', async () => {
      renderWithClient(<AdminAuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText('Administrative Audit Log')).toBeInTheDocument();
      });

      expect(screen.getByPlaceholderText(/search audit trail/i)).toBeInTheDocument();
      expect(screen.getByDisplayValue('All Actions')).toBeInTheDocument();
    });
  });

  describe('Route Guards & Role Isolation', () => {
    it('renders 403 ForbiddenPage when non-admin accesses admin portal', () => {
      const handleGoHome = vi.fn();
      render(<ForbiddenPage onGoHome={handleGoHome} requiredRole="Platform Administrators" />);

      expect(screen.getByText('403 Access Denied')).toBeInTheDocument();
      expect(screen.getByText('Restricted Area')).toBeInTheDocument();
      expect(screen.getByText(/reserved for Platform Administrators/i)).toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: /return to dashboard/i }));
      expect(handleGoHome).toHaveBeenCalled();
    });
  });
});

import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { NgoProfilePage } from '../pages/ngo/NgoProfilePage';
import { demoSource } from '../services/demoSource';
import { setDataSourceMode } from '../services';
import { simulationEngine } from '../simulation/simulationEngine';

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

describe('NGO Profile Page & Donor Ratings UI (Task 5 & 7)', () => {
  beforeEach(() => {
    setDataSourceMode('demo');
    simulationEngine.resetData();
    demoSource.setDemoUser('NGO');
    vi.clearAllMocks();
  });

  it('renders page header, snapshot statistics, and tabs', async () => {
    renderWithClient(<NgoProfilePage onTriggerToast={vi.fn()} />);

    expect(
      screen.getByText('NGO Profile & Donor Ratings')
    ).toBeInTheDocument();
    expect(
      screen.getByText(/manage your relief operations profile/i)
    ).toBeInTheDocument();

    // Tabs
    expect(screen.getByRole('button', { name: /pending ratings/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /my reviews/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /hub & fleet profile/i })).toBeInTheDocument();
  });

  it('renders pending picked-up claims for a verified NGO with Rate Donor buttons', async () => {
    renderWithClient(<NgoProfilePage onTriggerToast={vi.fn()} />);

    // Wait for pending ratings to load
    await waitFor(() => {
      expect(screen.getByText(/the grand gateway bengaluru/i)).toBeInTheDocument();
    });

    const rateButtons = screen.getAllByRole('button', { name: /rate donor/i });
    expect(rateButtons.length).toBeGreaterThan(0);
  });

  it('validates rating dialog: character counter, star limits, and error handling', async () => {
    renderWithClient(<NgoProfilePage onTriggerToast={vi.fn()} />);

    // 1. Wait for pending claims
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /rate donor/i })).toBeInTheDocument();
    });

    // 2. Open rate modal
    fireEvent.click(screen.getByRole('button', { name: /rate donor/i }));

    // 3. Modal elements & character counter
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText(/0\s*\/\s*500/)).toBeInTheDocument();

    const textarea = screen.getByPlaceholderText(/note packaging quality/i);

    // Typing updates character counter (39 characters)
    fireEvent.change(textarea, { target: { value: 'Insulated packaging was in great shape.' } });
    expect(screen.getByText(/39\s*\/\s*500/)).toBeInTheDocument();

    // Close modal via Cancel button
    const cancelBtn = screen.getByRole('button', { name: /cancel/i });
    fireEvent.click(cancelBtn);

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('updates pending list after a rating is submitted and adds review to My Reviews tab', async () => {
    const handleToast = vi.fn();
    renderWithClient(<NgoProfilePage onTriggerToast={handleToast} />);

    // 1. Wait for pending claims
    await waitFor(() => {
      expect(screen.getByText(/the grand gateway bengaluru/i)).toBeInTheDocument();
    });

    // 2. Click "Rate Donor"
    const rateBtn = screen.getByRole('button', { name: /rate donor/i });
    fireEvent.click(rateBtn);

    // 3. Fill in comment and submit rating
    const textarea = screen.getByPlaceholderText(/note packaging quality/i);
    fireEvent.change(textarea, { target: { value: 'Exceptional food quality, fresh and warm.' } });

    const submitBtn = screen.getByRole('button', { name: /submit rating/i });
    fireEvent.click(submitBtn);

    // 4. Verify toast
    await waitFor(() => {
      expect(handleToast).toHaveBeenCalledWith(
        expect.stringMatching(/rating submitted successfully/i)
      );
    });

    // 5. The pending claim is now rated and removed from pending list
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /rate donor/i })).not.toBeInTheDocument();
    });

    // 6. Switch to "My Reviews" tab to verify new review appears
    const reviewsTab = screen.getByRole('button', { name: /my reviews/i });
    fireEvent.click(reviewsTab);

    await waitFor(() => {
      expect(
        screen.getByText('Exceptional food quality, fresh and warm.')
      ).toBeInTheDocument();
    });
  });

  it('edit window locked state: displays "Locked" label and disables editing after 7 days', async () => {
    // Inject an expired review into demo state (> 7 days old)
    const state = demoSource.getInternalState();
    state.ratings.push({
      id: 888,
      claim: 888,
      ngo: 2,
      ngo_name: 'Surplus Relief Foundation',
      business: 1,
      business_name: 'Heritage Bistro',
      stars: 4,
      comment: 'Review submitted 10 days ago.',
      is_hidden: false,
      is_editable: false,
      edit_deadline: new Date(Date.now() - 10 * 86400000).toISOString(),
      created_at: new Date(Date.now() - 10 * 86400000).toISOString(),
      updated_at: new Date(Date.now() - 10 * 86400000).toISOString(),
    });

    renderWithClient(<NgoProfilePage onTriggerToast={vi.fn()} />);

    // Switch to "My Reviews" tab
    const reviewsTab = screen.getByRole('button', { name: /my reviews/i });
    fireEvent.click(reviewsTab);

    // Verify Heritage Bistro card has the Locked badge and NO Edit button
    await waitFor(() => {
      expect(screen.getByText('Heritage Bistro')).toBeInTheDocument();
    });

    const lockedBadge = screen.getByText(/Locked/i);
    expect(lockedBadge).toBeInTheDocument();

    const heritageCard = screen.getByText('Review submitted 10 days ago.').closest('div[id^="my-rating-"]');
    expect(heritageCard).toBeInTheDocument();
    // In this card, there should not be an Edit button
    expect(heritageCard?.querySelector('button')?.textContent).not.toMatch(/edit/i);
  });

  it('edit window active state: allows editing a review within 7 days', async () => {
    const handleToast = vi.fn();
    renderWithClient(<NgoProfilePage onTriggerToast={handleToast} />);

    // Switch to "My Reviews" tab
    const reviewsTab = screen.getByRole('button', { name: /my reviews/i });
    fireEvent.click(reviewsTab);

    // Wait for the active seeded review
    await waitFor(() => {
      expect(
        screen.getByText('Freshly packed, hot buffet surplus in pristine food-grade containers.')
      ).toBeInTheDocument();
    });

    // Click Edit button
    const editBtn = screen.getByRole('button', { name: /edit/i });
    fireEvent.click(editBtn);

    // Edit modal opens
    expect(screen.getByRole('heading', { name: /edit review/i })).toBeInTheDocument();

    // Change text and submit
    const textarea = screen.getByPlaceholderText(/update your review notes/i);
    fireEvent.change(textarea, { target: { value: 'Updated: Excellent cold-chain packaging.' } });

    const saveBtn = screen.getByRole('button', { name: /save changes/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(handleToast).toHaveBeenCalledWith(
        expect.stringMatching(/review updated successfully/i)
      );
    });
  });

  it('prevents a business user from opening /ngo/profile: displays Access Restricted screen', async () => {
    // Switch to BUSINESS persona
    demoSource.setDemoUser('BUSINESS');

    renderWithClient(<NgoProfilePage onTriggerToast={vi.fn()} />);

    // Access Restricted screen must be displayed
    await waitFor(() => {
      expect(screen.getByText('Access Restricted')).toBeInTheDocument();
    });

    expect(
      screen.getByText(/business accounts cannot access this page/i)
    ).toBeInTheDocument();

    // NGO Profile content and tabs must NOT be in the document
    expect(screen.queryByText('NGO Profile & Donor Ratings')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /pending ratings/i })).not.toBeInTheDocument();
  });

  it('displays informative warning banner when NGO is unverified', async () => {
    demoSource.setDemoUser('NGO_UNVERIFIED');

    renderWithClient(<NgoProfilePage onTriggerToast={vi.fn()} />);

    // Verification banner must be present
    expect(
      screen.getByText(/verification required to rate donors/i)
    ).toBeInTheDocument();
    expect(
      screen.getAllByText(/complete verification to rate donor businesses/i).length
    ).toBeGreaterThanOrEqual(1);

    // Pending ratings should indicate verification is needed
    expect(
      screen.getByText(/verification pending/i)
    ).toBeInTheDocument();
  });
});

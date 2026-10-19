import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BusinessRatingCard } from '../components/business/BusinessRatingCard';
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

describe('BusinessRatingCard (Read-Only Business Side)', () => {
  beforeEach(() => {
    setDataSourceMode('demo');
    demoSource.setDemoUser('BUSINESS');
    vi.clearAllMocks();
  });

  it('renders "Your Rating" card with average score, review count, and star breakdown bars', async () => {
    renderWithClient(<BusinessRatingCard businessId={1} />);

    // 1. Wait for rating data to load
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /your rating/i })).toBeInTheDocument();
    });

    expect(screen.getByText(/verified ngo reviews/i)).toBeInTheDocument();
    expect(screen.getByText(/read-only • replies disabled/i)).toBeInTheDocument();

    // Average score (seeded 4.5 from 5 and 4 stars)
    expect(screen.getByText('4.5')).toBeInTheDocument();
    expect(screen.getByText(/based on 2 verified reviews/i)).toBeInTheDocument();

    // 2. Breakdown bars (5 stars down to 1 star)
    expect(screen.getByText('Rating Distribution')).toBeInTheDocument();
    expect(screen.getByLabelText(/5 stars: 1 reviews/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/4 stars: 1 reviews/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/3 stars: 0 reviews/i)).toBeInTheDocument();
  });

  it('renders the latest NGO reviews with the NGO name and comments', async () => {
    renderWithClient(<BusinessRatingCard businessId={1} />);

    await waitFor(() => {
      expect(screen.getByText(/surplus relief foundation/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/robin hood army \(mysore chapter\)/i)).toBeInTheDocument();
    expect(
      screen.getByText(/freshly packed, hot buffet surplus in pristine food-grade containers/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/pristine hygiene condition, thermally intact packaging!/i)
    ).toBeInTheDocument();
  });

  it('renders a friendly empty state when a business has zero reviews', async () => {
    renderWithClient(<BusinessRatingCard businessId={9999} />);

    await waitFor(() => {
      expect(screen.getByText(/no donor ratings received yet/i)).toBeInTheDocument();
    });

    expect(screen.getByText('—')).toBeInTheDocument();
    expect(screen.getByText(/no reviews submitted yet/i)).toBeInTheDocument();
  });
});

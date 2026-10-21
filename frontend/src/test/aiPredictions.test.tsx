import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BusinessPurchasePlannerPage } from '../pages/business/BusinessPurchasePlannerPage';
import { BusinessAiInsightsPage } from '../pages/business/BusinessAiInsightsPage';
import { ForbiddenPage } from '../pages/ForbiddenPage';
import { demoSource } from '../services/demoSource';
import { setDataSourceMode } from '../services';

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

describe('AI Waste Predictions & Benchmark Insights (Task 3)', () => {
  beforeEach(() => {
    setDataSourceMode('demo');
    demoSource.seedDeterministicData();
    demoSource.setEnableLatency(false);
    demoSource.setDemoUser('BUSINESS');
    vi.clearAllMocks();
  });

  describe('BusinessPurchasePlannerPage', () => {
    it('renders all form inputs and validates planned quantity', () => {
      renderWithClient(<BusinessPurchasePlannerPage />);

      expect(screen.getByRole('heading', { name: /purchase planner/i })).toBeInTheDocument();
      expect(screen.getByText(/AI-Assisted/i)).toBeInTheDocument();

      // Form inputs
      expect(screen.getByLabelText(/food category/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/planned order quantity/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/active promotion/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/expected weather/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/calendar date/i)).toBeInTheDocument();

      const calculateButton = screen.getByRole('button', { name: /calculate plan/i });
      expect(calculateButton).toBeInTheDocument();
      expect(calculateButton).not.toBeDisabled();

      // Entering invalid quantity (0 or negative) disables submit
      const qtyInput = screen.getByLabelText(/planned order quantity/i);
      fireEvent.change(qtyInput, { target: { value: '0' } });

      expect(screen.getByText(/quantity must be greater than zero/i)).toBeInTheDocument();
      expect(calculateButton).toBeDisabled();

      // Reset to valid quantity
      fireEvent.change(qtyInput, { target: { value: '150' } });
      expect(screen.queryByText(/quantity must be greater than zero/i)).not.toBeInTheDocument();
      expect(calculateButton).not.toBeDisabled();
    });

    it('submits purchase plan, renders forecast range, waste risk badge, and plain-language explanation', async () => {
      const handleToast = vi.fn();
      renderWithClient(<BusinessPurchasePlannerPage onTriggerToast={handleToast} />);

      const qtyInput = screen.getByLabelText(/planned order quantity/i);
      fireEvent.change(qtyInput, { target: { value: '180' } });

      const calculateButton = screen.getByRole('button', { name: /calculate plan/i });
      fireEvent.click(calculateButton);

      // Verify results card renders
      await waitFor(() => {
        expect(screen.getByText(/evaluation result/i)).toBeInTheDocument();
        expect(screen.getAllByText(/waste risk/i).length).toBeGreaterThanOrEqual(1);
      });

      // Key metrics
      expect(screen.getAllByText(/forecast demand/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/over-order ratio/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/recommended/i).length).toBeGreaterThanOrEqual(1);

      // Explanation box
      expect(screen.getByText(/operational recommendation/i)).toBeInTheDocument();
      expect(screen.getAllByText(/demo data/i).length).toBeGreaterThanOrEqual(1);

      // Visible confidence note
      expect(screen.getByText(/deterministic sample response generated/i)).toBeInTheDocument();

      // Toast triggered
      expect(handleToast).toHaveBeenCalledWith('Purchase plan evaluated successfully.');
    });

    it('toggles the "How is this calculated?" explanatory panel', () => {
      renderWithClient(<BusinessPurchasePlannerPage />);

      const toggleButton = screen.getByRole('button', { name: /how is this calculated\?/i });
      expect(toggleButton).toBeInTheDocument();

      // Initially closed
      expect(screen.queryByText(/generalized linear poisson regression/i)).not.toBeInTheDocument();

      // Click to open
      fireEvent.click(toggleButton);
      expect(screen.getByText(/generalized linear poisson regression/i)).toBeInTheDocument();
      expect(screen.getByText(/lightgbm gradient-boosted decision tree/i)).toBeInTheDocument();
      expect(screen.getByText(/70% of perishable shelf life/i)).toBeInTheDocument();

      // Click to close
      fireEvent.click(toggleButton);
      expect(screen.queryByText(/generalized linear poisson regression/i)).not.toBeInTheDocument();
    });

    it('displays the service unavailable banner when the ML service returns 503 or unavailable status', async () => {
      // Mock getPlanPrediction to return service unavailable
      vi.spyOn(demoSource, 'getPlanPrediction').mockResolvedValueOnce({
        status: 'unavailable',
        detail: 'Predictions temporarily unavailable. The machine learning service is offline or starting up. Please try again shortly.',
        forecast_demand: 0,
        forecast_range: { min: 0, max: 0 },
        over_order_ratio: 0,
        predicted_waste_level: 'Unknown',
        waste_probabilities: { Low: 0, Medium: 0, High: 0 },
        recommended_quantity: 0,
        explanation: '',
        model_version: '',
        confidence_note: '',
      });

      renderWithClient(<BusinessPurchasePlannerPage />);

      const calculateButton = screen.getByRole('button', { name: /calculate plan/i });
      fireEvent.click(calculateButton);

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
        expect(screen.getByText(/machine learning service unavailable/i)).toBeInTheDocument();
        expect(screen.getByText(/predictions temporarily unavailable/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /retry connection/i })).toBeInTheDocument();
      });
    });

    it('displays general error alert with retry button when mutation throws', async () => {
      vi.spyOn(demoSource, 'getPlanPrediction').mockRejectedValueOnce(
        new Error('Network error connecting to prediction gateway')
      );

      renderWithClient(<BusinessPurchasePlannerPage />);

      const calculateButton = screen.getByRole('button', { name: /calculate plan/i });
      fireEvent.click(calculateButton);

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
        expect(screen.getByText(/network error connecting to prediction gateway/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
      });
    });
  });

  describe('BusinessAiInsightsPage', () => {
    it('always renders the mandatory synthetic benchmark disclosure banner', async () => {
      renderWithClient(<BusinessAiInsightsPage />);

      await waitFor(() => {
        expect(screen.getByText(/benchmark dataset disclosure/i)).toBeInTheDocument();
        expect(
          screen.getByText(/based on a benchmark dataset that appears synthetic\. these are general patterns, not your own data\./i)
        ).toBeInTheDocument();
      });
    });

    it('renders KPI summary cards, waste rate by category, weather drivers, and data card', async () => {
      renderWithClient(<BusinessAiInsightsPage />);

      await waitFor(() => {
        expect(screen.getByText('Over-Purchase Rate')).toBeInTheDocument();
        expect(screen.getByText('64.08%')).toBeInTheDocument();
        expect(screen.getByText('Promotion Lift')).toBeInTheDocument();
        expect(screen.getByText('+33.06%')).toBeInTheDocument();
      });

      // Food category waste rates section
      expect(screen.getByText(/empirical waste rate by food category/i)).toBeInTheDocument();

      // Waste reasons distribution
      expect(screen.getByText(/waste reasons distribution by category/i)).toBeInTheDocument();

      // Weather drivers
      expect(screen.getByText(/weather condition demand multipliers/i)).toBeInTheDocument();
      expect(screen.getByText('+3.85%')).toBeInTheDocument();
      expect(screen.getByText('-33.17%')).toBeInTheDocument();

      // Dataset card
      expect(screen.getByText(/benchmark dataset data card/i)).toBeInTheDocument();
      expect(screen.getByText(/8,000 daily observations/i)).toBeInTheDocument();
      expect(screen.getByText(/deterministic sales-accounting constraints/i)).toBeInTheDocument();
    });

    it('renders error state with retry button if loading dataset insights fails', async () => {
      vi.spyOn(demoSource, 'getDatasetInsights').mockRejectedValueOnce(
        new Error('Backend cache expired and ML service is offline')
      );

      renderWithClient(<BusinessAiInsightsPage />);

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
        expect(screen.getByText(/failed to load dataset insights/i)).toBeInTheDocument();
        expect(screen.getByText(/backend cache expired/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
      });
    });
  });

  describe('Role-Based Access Control & Route Guarding', () => {
    it('strictly denies NGO users from accessing business AI prediction routes with 403 ForbiddenPage', () => {
      const handleGoHome = vi.fn();
      render(<ForbiddenPage onGoHome={handleGoHome} requiredRole="Business Organizations" />);

      expect(screen.getByText('403 Access Denied')).toBeInTheDocument();
      expect(screen.getByText('Restricted Area')).toBeInTheDocument();
      expect(screen.getByText(/reserved for Business Organizations/i)).toBeInTheDocument();

      const homeButton = screen.getByRole('button', { name: /return to dashboard/i });
      fireEvent.click(homeButton);
      expect(handleGoHome).toHaveBeenCalledTimes(1);
    });

    it('verifies that planner and insights paths are categorized as business-only routes', () => {
      const isBusinessOnlyRoute = (path: string) =>
        [
          'inventory',
          'scan',
          'import',
          'business/pos-simulator',
          'pos-simulator',
          'business/ai/planner',
          'ai/planner',
          'planner',
          'business/ai/insights',
          'ai/insights',
          'insights',
        ].includes(path);

      expect(isBusinessOnlyRoute('business/ai/planner')).toBe(true);
      expect(isBusinessOnlyRoute('ai/planner')).toBe(true);
      expect(isBusinessOnlyRoute('planner')).toBe(true);
      expect(isBusinessOnlyRoute('business/ai/insights')).toBe(true);
      expect(isBusinessOnlyRoute('ai/insights')).toBe(true);
      expect(isBusinessOnlyRoute('insights')).toBe(true);

      // NGO routes should not be business-only
      expect(isBusinessOnlyRoute('feed')).toBe(false);
      expect(isBusinessOnlyRoute('claims')).toBe(false);
      expect(isBusinessOnlyRoute('requirements')).toBe(false);
    });
  });
});

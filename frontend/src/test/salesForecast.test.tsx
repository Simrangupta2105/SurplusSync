import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SalesForecastCard } from '../components/business/SalesForecastCard';
import { BusinessForecastPage } from '../pages/business/BusinessForecastPage';
import { demoSource } from '../services';

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: Infinity,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

function renderWithClient(ui: React.ReactElement) {
  const testClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={testClient}>
      {ui}
    </QueryClientProvider>
  );
}

describe('Recent Sales & Demand Forecast Trajectory (Task 3)', () => {
  describe('DemoSource Recent Sales Provider', () => {
    it('returns realistic past-7-days sales with correct schema and unbroken dates', async () => {
      const sales = await demoSource.getRecentSales({ days: 7, category: 'Dairy' });
      expect(sales).toHaveLength(7);
      sales.forEach((s) => {
        expect(s).toHaveProperty('date');
        expect(s).toHaveProperty('category', 'Dairy');
        expect(s.units_sold).toBeGreaterThan(0);
        expect(s.revenue).toBeGreaterThan(0);
        expect(s.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      });
    });

    it('returns 14 days when requested and aggregates across categories for All', async () => {
      const sales = await demoSource.getRecentSales({ days: 14, category: 'All' });
      expect(sales).toHaveLength(14);
      sales.forEach((s) => {
        expect(s.category).toBe('All');
        expect(s.units_sold).toBeGreaterThan(300); // Aggregate across categories
      });
    });
  });

  describe('SalesForecastCard Component', () => {
    it('renders the card header, model badge, and category selector tabs', async () => {
      renderWithClient(<SalesForecastCard onNavigate={() => {}} />);

      expect(screen.getByText(/recent sales & demand forecast/i)).toBeInTheDocument();
      expect(screen.getByText(/histgradientboostingdemandmodel/i)).toBeInTheDocument();

      // Check category selector tabs
      expect(screen.getByRole('tab', { name: /^All$/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /^Dairy$/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /^Bakery$/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /^Vegetables$/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /^Meat$/i })).toBeInTheDocument();
    });

    it('updates active category tab when a user clicks another category', async () => {
      renderWithClient(<SalesForecastCard onNavigate={() => {}} />);

      const dairyTab = screen.getByRole('tab', { name: /^Dairy$/i });
      fireEvent.click(dairyTab);
      expect(dairyTab).toHaveAttribute('aria-selected', 'true');

      const bakeryTab = screen.getByRole('tab', { name: /^Bakery$/i });
      fireEvent.click(bakeryTab);
      expect(bakeryTab).toHaveAttribute('aria-selected', 'true');
      expect(dairyTab).toHaveAttribute('aria-selected', 'false');
    });

    it('navigates to /business/ai/forecast when clicking Explore Full Forecast Engine', async () => {
      const onNavigateMock = vi.fn();
      renderWithClient(<SalesForecastCard onNavigate={onNavigateMock} />);

      const exploreBtn = screen.getByRole('button', { name: /explore full forecast engine/i });
      fireEvent.click(exploreBtn);
      expect(onNavigateMock).toHaveBeenCalledWith('business/ai/forecast');
    });

    it('handles empty sales gracefully without crashing', async () => {
      vi.spyOn(demoSource, 'getRecentSales').mockResolvedValueOnce([]);

      renderWithClient(<SalesForecastCard onNavigate={() => {}} />);

      expect(screen.getByText(/recent sales & demand forecast/i)).toBeInTheDocument();
      expect(screen.getByText(/0 units\/day/i)).toBeInTheDocument();
    });
  });

  describe('BusinessForecastPage Component', () => {
    it('renders page header, cockpit KPI stat cards, and model explanation', async () => {
      renderWithClient(<BusinessForecastPage onNavigate={() => {}} />);

      // Page Title
      expect(screen.getByText(/ai sales & demand forecasting/i)).toBeInTheDocument();

      // Stat Cards
      expect(screen.getByText(/past avg\. daily sales/i)).toBeInTheDocument();
      expect(screen.getByText(/forecasted daily demand/i)).toBeInTheDocument();
      expect(screen.getByText(/demand momentum shift/i)).toBeInTheDocument();
      expect(screen.getByText(/production serving model/i)).toBeInTheDocument();

      // Model explanation
      expect(screen.getByText(/model intelligence & operational explanation/i)).toBeInTheDocument();
      expect(screen.getByText(/empirical feature drivers/i)).toBeInTheDocument();
    });

    it('allows toggling between 7 Days and 14 Days forecast horizons', async () => {
      renderWithClient(<BusinessForecastPage onNavigate={() => {}} />);

      const sevenDaysBtn = screen.getByRole('button', { name: /^7 days$/i });
      const fourteenDaysBtn = screen.getByRole('button', { name: /^14 days$/i });

      expect(sevenDaysBtn).toBeInTheDocument();
      expect(fourteenDaysBtn).toBeInTheDocument();

      fireEvent.click(fourteenDaysBtn);
      expect(screen.getByText(/past 14 days actuals/i)).toBeInTheDocument();

      fireEvent.click(sevenDaysBtn);
      expect(screen.getByText(/past 7 days actuals/i)).toBeInTheDocument();
    });

    it('clicking Launch Purchase Planner navigates to business/ai/planner', async () => {
      const onNavigateMock = vi.fn();
      renderWithClient(<BusinessForecastPage onNavigate={onNavigateMock} />);

      const plannerBtn = screen.getByRole('button', { name: /launch purchase planner/i });
      fireEvent.click(plannerBtn);
      expect(onNavigateMock).toHaveBeenCalledWith('business/ai/planner');
    });
  });
});

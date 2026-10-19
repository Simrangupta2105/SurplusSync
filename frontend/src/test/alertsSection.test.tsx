import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BusinessAlertsPage } from '../pages/business/BusinessAlertsPage';
import { demoSource } from '../services/demoSource';
import { setDataSourceMode } from '../services';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false, gcTime: 0 },
  },
});

const renderWithProviders = (ui: React.ReactElement) => {
  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  );
};

describe('Alerts Section - Expired Items Exclusion', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem('surplussync_data_mode', 'demo');
    setDataSourceMode('demo');
    queryClient.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('guarantees demoSource.getAlerts excludes batches that are expired', async () => {
    const alerts = await demoSource.getAlerts();
    const todayStr = new Date().toISOString().split('T')[0];

    // Verify none of the returned alerts are for expired batches
    alerts.forEach((alert) => {
      expect(alert.batch_status).not.toBe('EXPIRED');
      if (alert.expiry_date) {
        expect(alert.expiry_date >= todayStr).toBe(true);
      }
      expect(alert.message.toLowerCase()).not.toContain('expired on');
    });
  });

  it('automatically removes alerts when a batch expires', async () => {
    const state = demoSource.getInternalState();

    // Inject an active batch that expires in 1 day with an alert
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowStr = tomorrow.toISOString().split('T')[0];

    state.batches.push({
      id: 9999,
      organization: 1,
      product: 1,
      location: 1,
      batch_code: 'BTH-TEST-9999',
      quantity: '10.0',
      received_date: '2026-10-10',
      expiry_date: tomorrowStr,
      status: 'ACTIVE',
      created_at: new Date().toISOString(),
    });

    state.alerts.unshift({
      id: 8888,
      organization: 1,
      batch: 9999,
      rule: 1,
      severity: 'CRITICAL',
      message: 'Batch BTH-TEST-9999 expires tomorrow',
      is_acknowledged: false,
      created_at: new Date().toISOString(),
    });

    // Before expiring: alert should be returned
    let alerts = await demoSource.getAlerts();
    expect(alerts.some((a) => a.id === 8888)).toBe(true);

    // Now transition batch to EXPIRED
    const testBatch = state.batches.find((b) => b.id === 9999);
    if (testBatch) {
      testBatch.status = 'EXPIRED';
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      testBatch.expiry_date = yesterday.toISOString().split('T')[0];
    }

    // After expiring: alert MUST NOT be in the alert section
    alerts = await demoSource.getAlerts();
    expect(alerts.some((a) => a.id === 8888)).toBe(false);
    expect(alerts.some((a) => a.batch === 9999)).toBe(false);
  });

  it('filters out any expired batches from BusinessAlertsPage rendering', async () => {
    const handleToast = vi.fn();
    renderWithProviders(<BusinessAlertsPage onTriggerToast={handleToast} />);

    await waitFor(() => {
      // Expect page header to be rendered
      expect(screen.getByText('Stock & Spoilage Alerts')).toBeInTheDocument();
    });

    // Verify no "EXPIRED" messages are displayed
    const expiredElements = screen.queryAllByText(/expired on/i);
    expect(expiredElements).toHaveLength(0);
  });
});

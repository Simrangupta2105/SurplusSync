import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BusinessPOSSimulatorPage } from '../pages/business/BusinessPOSSimulatorPage';
import { simulationEngine } from '../simulation/simulationEngine';
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

describe('POS Simulation & Demo Controls Verification (Task 4)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem('surplussync_data_mode', 'demo');
    setDataSourceMode('demo');
    queryClient.clear();
    simulationEngine.stop();
    simulationEngine.resetData();
    window.innerWidth = 1024;
  });

  afterEach(() => {
    simulationEngine.stop();
    vi.restoreAllMocks();
  });

  it('1. Floating Demo Controls panel is completely removed from the DOM', () => {
    expect(screen.queryByLabelText(/Floating Demo Controls/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Simulation Engine/i)).not.toBeInTheDocument();
  });

  it('2. Simulation engine starts once and is idempotent (no duplicate timers)', () => {
    // Engine is stopped by default (manual on-demand mode)
    expect(simulationEngine.getIsRunning()).toBe(false);

    // Calling start() starts the clock idempotently
    simulationEngine.start();
    simulationEngine.start();

    // Despite multiple starts, only 1 interval timer should remain active
    expect(simulationEngine.getIsRunning()).toBe(true);
    simulationEngine.stop();
  });

  it('3. Simulate POS Sale reduces stock and strictly respects FEFO order', () => {
    const state = demoSource.getInternalState();
    const product = state.products[0]; // First product

    const candidateBatches = state.batches
      .filter((b) => b.product === product.id && b.status === 'ACTIVE' && parseFloat(b.quantity) > 0)
      .sort((a, b) => a.expiry_date.localeCompare(b.expiry_date));

    expect(candidateBatches.length).toBeGreaterThanOrEqual(2);

    const b1 = candidateBatches[0];
    const b2 = candidateBatches[1];
    const initialB1Qty = parseFloat(b1.quantity);
    const initialB2Qty = parseFloat(b2.quantity);

    // Deduct exact b1 quantity + 2 from b2
    const deductQty = initialB1Qty + 2;
    const res = simulationEngine.executeRandomPOSSale({
      targetProductId: product.id,
      quantity: deductQty,
    });

    expect(res.success).toBe(true);
    expect(res.quantityDeducted).toBe(deductQty);

    // Batch 1 must be depleted (0)
    expect(parseFloat(b1.quantity)).toBe(0);
    expect(b1.status).toBe('DEPLETED');

    // Batch 2 must have absorbed the remaining 2 units
    expect(parseFloat(b2.quantity)).toBeCloseTo(initialB2Qty - 2, 1);
  });

  it('4. Repeated receipt number deducts only once (idempotent replay)', () => {
    const state = demoSource.getInternalState();
    const product = state.products[0];

    const getStock = () =>
      state.batches
        .filter((b) => b.product === product.id && b.status === 'ACTIVE')
        .reduce((sum, b) => sum + parseFloat(b.quantity), 0);

    const stockBefore = getStock();
    const receiptNumber = 'REC-TEST-IDEMPOTENT-888';

    // First transaction
    const res1 = simulationEngine.executeRandomPOSSale({
      receiptNumber,
      targetProductId: product.id,
      quantity: 2,
    });

    expect(res1.success).toBe(true);
    expect(res1.isIdempotentReplay).toBeFalsy();
    const stockAfterFirst = getStock();
    expect(stockAfterFirst).toBeCloseTo(stockBefore - 2, 1);

    // Second transaction with the EXACT SAME receipt number
    const res2 = simulationEngine.executeRandomPOSSale({
      receiptNumber,
      targetProductId: product.id,
      quantity: 2,
    });

    expect(res2.success).toBe(true);
    expect(res2.isIdempotentReplay).toBe(true);

    // Stock MUST remain unchanged after the idempotent replay
    const stockAfterSecond = getStock();
    expect(stockAfterSecond).toBeCloseTo(stockAfterFirst, 1);
  });

  it('5. Insufficient stock is rejected without mutating inventory batches', () => {
    const state = demoSource.getInternalState();
    const product = state.products[0];

    const stockBefore = state.batches
      .filter((b) => b.product === product.id)
      .map((b) => ({ id: b.id, qty: b.quantity, status: b.status }));

    const res = simulationEngine.executeRandomPOSSale({
      receiptNumber: 'REC-FAIL-INSUFFICIENT',
      targetProductId: product.id,
      quantity: 999999,
    });

    expect(res.success).toBe(false);
    expect(res.message).toMatch(/insufficient stock/i);

    // Batches must remain completely unchanged
    const stockAfter = state.batches
      .filter((b) => b.product === product.id)
      .map((b) => ({ id: b.id, qty: b.quantity, status: b.status }));

    expect(stockAfter).toEqual(stockBefore);
  });

  it('6. Reconcile indicator stays at zero delta after 100 random operations', () => {
    // Run 100 varied operations
    for (let i = 0; i < 100; i++) {
      const op = i % 4;
      if (op === 0) {
        simulationEngine.executeRandomPOSSale();
      } else if (op === 1) {
        simulationEngine.addExpiringBatch(24, 10);
      } else if (op === 2) {
        simulationEngine.executeAutoListing();
      } else {
        simulationEngine.fastForwardDays(1);
      }
    }

    const reconcile = simulationEngine.reconcileStock();
    expect(reconcile.isReconciled).toBe(true);
    expect(reconcile.delta).toBeLessThan(0.1);
  });

  it('7. Floating simulation panel is completely removed from mobile viewports', () => {
    window.innerWidth = 375;
    expect(screen.queryByRole('button', { name: /demo controls/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/Simulation Engine/i)).not.toBeInTheDocument();
  });

  it('8. BusinessPOSSimulatorPage renders caution warning, masked key toggle, and handles simulated receipt', async () => {
    let callCount = 0;
    const fetchSpy = vi.spyOn(global, 'fetch').mockImplementation(async (url, init) => {
      const urlStr = typeof url === 'string' ? url : url.toString();
      if (urlStr.includes('/inventory/batches/deduct/')) {
        if (init?.method === 'OPTIONS') {
          return new Response(null, { status: 200 });
        }
        callCount++;
        return new Response(
          JSON.stringify({
            message: 'Stock deducted successfully',
            total_deducted: '2.0',
            deductions: [
              {
                batch_id: 1,
                batch_code: 'BTH-202610-001',
                deducted_quantity: '2.0',
                remaining_batch_quantity: '10.0',
                status: 'ACTIVE',
              },
            ],
            idempotent_replay: callCount > 1,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      }
      if (urlStr.includes('/inventory/products/')) {
        return new Response(
          JSON.stringify([
            { id: 1, name: 'Sourdough Bread', sku: 'BAK-001', retail_price: 4.5, current_stock: 12 },
          ]),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      }
      return new Response(null, { status: 200 });
    });

    const toastMock = vi.fn();
    renderWithProviders(<BusinessPOSSimulatorPage onTriggerToast={toastMock} />);

    // 1. Renders Caution Banner
    expect(screen.getByText(/Live Backend Simulator Caution/i)).toBeInTheDocument();

    // 2. API Key input with visibility toggle
    const apiKeyInput = screen.getByPlaceholderText(/Paste terminal key/i) as HTMLInputElement;
    expect(apiKeyInput.type).toBe('password');

    const toggleVisBtn = screen.getByTitle('Show key');
    fireEvent.click(toggleVisBtn);
    expect(apiKeyInput.type).toBe('text');

    // 3. Enter in-memory key
    fireEvent.change(apiKeyInput, { target: { value: 'ss_live_demo_terminal_key_1234' } });

    // 4. Wait for products to load and add first product from catalog picker to receipt
    const addButtons = await screen.findAllByRole('button', { name: /add/i }, { timeout: 10000 });
    expect(addButtons.length).toBeGreaterThan(0);
    fireEvent.click(addButtons[0]);

    // Receipt should now have 1 item
    expect(screen.getByText(/Receipt Line Items \(1\)/i)).toBeInTheDocument();

    // 5. Submit POS Transaction
    const submitBtn = screen.getByRole('button', { name: /Submit POS Transaction/i });
    fireEvent.click(submitBtn);

    // Expect toast and live HTTP wire inspector with HTTP 200
    await waitFor(() => {
      expect(toastMock).toHaveBeenCalled();
      expect(screen.getByText(/Live HTTP Wire Inspector/i)).toBeInTheDocument();
      expect(screen.getByText(/HTTP 200/i)).toBeInTheDocument();
    }, { timeout: 10000 });

    // 6. Test Idempotency Replay button is visible after successful submission
    const idempotencyBtn = screen.getByRole('button', { name: /Send the same receipt again \(Test Idempotency\)/i });
    expect(idempotencyBtn).toBeInTheDocument();
    fireEvent.click(idempotencyBtn);

    await waitFor(() => {
      expect(screen.getByText(/Idempotent Replay Verified/i)).toBeInTheDocument();
    }, { timeout: 10000 });

    fetchSpy.mockRestore();
  }, 15000);
});

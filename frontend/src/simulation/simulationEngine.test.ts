import { describe, it, expect, beforeEach } from 'vitest';
import { SimulationEngine } from './simulationEngine';
import { demoSource } from '../services/demoSource';

describe('SimulationEngine & Stock Invariant Verification', () => {
  let engine: SimulationEngine;

  beforeEach(() => {
    engine = new SimulationEngine();
    engine.resetData();
  });

  it('proves stock totals always reconcile (received = sold + discarded + donated + remaining)', () => {
    // Check initial state reconciliation
    const initialReconcile = engine.reconcileStock();
    expect(initialReconcile.isReconciled).toBe(true);
    expect(initialReconcile.delta).toBeLessThan(0.1);

    // Perform 10 simulated POS sales
    for (let i = 0; i < 10; i++) {
      engine.executeRandomPOSSale();
    }

    // Reconcile after 10 sales
    const postSalesReconcile = engine.reconcileStock();
    expect(postSalesReconcile.isReconciled).toBe(true);
    expect(
      Math.abs(
        postSalesReconcile.received -
          (postSalesReconcile.sold +
            postSalesReconcile.discarded +
            postSalesReconcile.donated +
            postSalesReconcile.remaining)
      )
    ).toBeLessThan(0.1);

    // Add an expiring batch and reconcile
    engine.addExpiringBatch(24, 30);
    const postBatchReconcile = engine.reconcileStock();
    expect(postBatchReconcile.isReconciled).toBe(true);
  });

  it('proves FEFO order is strictly respected during stock deductions', () => {
    const state = demoSource.getInternalState();
    const product = state.products[0]; // Nandini Milk

    // Find all active batches for this product
    const batches = state.batches
      .filter((b) => b.product === product.id && b.status === 'ACTIVE' && parseFloat(b.quantity) > 0)
      .sort((a, b) => a.expiry_date.localeCompare(b.expiry_date));

    expect(batches.length).toBeGreaterThanOrEqual(2);

    const firstBatch = batches[0];
    const secondBatch = batches[1];
    const initialFirstQty = parseFloat(firstBatch.quantity);
    const initialSecondQty = parseFloat(secondBatch.quantity);

    // Deduct slightly less than first batch quantity
    const smallDeductQty = Math.floor(initialFirstQty / 2);
    engine.executeRandomPOSSale(product.id, smallDeductQty);

    // First batch should have decreased, second batch MUST be completely untouched!
    expect(parseFloat(firstBatch.quantity)).toBeCloseTo(initialFirstQty - smallDeductQty, 1);
    expect(parseFloat(secondBatch.quantity)).toBeCloseTo(initialSecondQty, 1);

    // Deduct the remainder of first batch PLUS some of second batch
    const remainingInFirst = parseFloat(firstBatch.quantity);
    const spilloverQty = 5;
    const totalToDeduct = remainingInFirst + spilloverQty;

    engine.executeRandomPOSSale(product.id, totalToDeduct);

    // First batch must now be 0 (DEPLETED)
    expect(parseFloat(firstBatch.quantity)).toBe(0);
    expect(firstBatch.status).toBe('DEPLETED');

    // Second batch must have absorbed the spillover
    expect(parseFloat(secondBatch.quantity)).toBeCloseTo(initialSecondQty - spilloverQty, 1);
  });

  it('proves fast-forward advances virtual clock and marks past batches as EXPIRED', () => {
    const initialTime = engine.getVirtualTime();
    engine.fastForwardDays(5);
    const newTime = engine.getVirtualTime();

    // Virtual time should have advanced by 5 days (5 * 24h)
    const diffMs = newTime.getTime() - initialTime.getTime();
    expect(diffMs).toBe(5 * 24 * 3600 * 1000);

    // Post fast-forward reconciliation must still hold true
    const reconcile = engine.reconcileStock();
    expect(reconcile.isReconciled).toBe(true);
  });

  it('proves claim lifecycle progression (PENDING -> CONFIRMED -> PICKED_UP)', () => {
    const state = demoSource.getInternalState();

    // Add a new PENDING claim
    state.claims.unshift({
      id: 9999,
      listing_id: 1,
      ngo_id: 1,
      ngo_name: 'Surplus Relief Foundation',
      status: 'PENDING',
      pickup_eta: '22:00',
      notes: 'Test pickup',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });

    // Step 1: Advance pending -> confirmed
    const step1 = engine.advanceOldestClaim();
    expect(step1.success).toBe(true);
    const claim = state.claims.find((c) => c.id === 9999);
    expect(claim?.status).toBe('CONFIRMED');

    // Step 2: Advance confirmed -> picked up
    const step2 = engine.advanceOldestClaim();
    expect(step2.success).toBe(true);
    expect(claim?.status).toBe('PICKED_UP');
  });
});

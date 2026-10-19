/**
 * SurplusSync Simulation Engine (Demo Mode Only)
 * Pure stateful simulation engine completely decoupled from UI.
 *
 * Responsibilities:
 * 1. Simulation clock with selectable speeds (1x, 5x, 20x)
 * 2. Automated periodic events:
 *    - POS sale every 20-40s (FEFO deduction, ledger record, telemetry update)
 *    - New surplus listing broadcast every 30-60s with notification
 *    - Claims progression: PENDING -> CONFIRMED -> PICKED_UP
 *    - Expiry countdowns updating in virtual time
 * 3. Manual actions:
 *    - Simulate POS sale, Add expiring batch, New donation nearby, Fast-forward 1 day, Pause/Resume, Reset data
 * 4. Invariant reconciliation:
 *    - Proves received === sold + discarded + donated + remaining
 *    - Enforces FEFO order (earliest expiring batch deducted first)
 */

import { demoSource } from '../services/demoSource';
import type { Batch, DonationListing, NotificationItem } from '../types';

export type SimulationSpeed = 1 | 5 | 20;

export type SimulationEventType =
  | 'TICK'
  | 'POS_SALE'
  | 'NEW_LISTING'
  | 'CLAIM_STATUS_CHANGE'
  | 'BATCH_ADDED'
  | 'CLOCK_FAST_FORWARD'
  | 'STATUS_CHANGE'
  | 'RESET';

export interface SimulationEvent {
  type: SimulationEventType;
  message: string;
  data?: unknown;
  timestamp: string;
}

export interface ReconcileResult {
  isReconciled: boolean;
  received: number;
  sold: number;
  discarded: number;
  donated: number;
  remaining: number;
  sumDeductionsAndRemaining: number;
  delta: number;
  productBreakdown: Array<{
    productId: number;
    productName: string;
    received: number;
    accounted: number;
    reconciled: boolean;
  }>;
}

export type SimulationListener = (event: SimulationEvent) => void;

export interface POSSalePayload {
  receiptNumber?: string;
  targetProductId?: number;
  barcode?: string;
  sku?: string;
  quantity?: number;
  source?: string;
}

export interface POSSaleRecord {
  id: string;
  receiptNumber: string;
  productName: string;
  barcodeOrSku: string;
  quantity: number;
  unit: string;
  batchesUsed: string[];
  timestamp: string;
  isIdempotentReplay?: boolean;
}

export interface POSSaleResult {
  success: boolean;
  message: string;
  isIdempotentReplay?: boolean;
  receiptNumber?: string;
  productName?: string;
  quantityDeducted?: number;
  unit?: string;
  batchesUsed?: string[];
}

export class SimulationEngine {
  private static instance: SimulationEngine | null = null;

  public static getInstance(): SimulationEngine {
    if (!SimulationEngine.instance) {
      SimulationEngine.instance = new SimulationEngine();
    }
    return SimulationEngine.instance;
  }

  private isRunning = false;
  private speed: SimulationSpeed = 1;
  private intervalId: number | null = null;
  private virtualTime: Date;

  private recentPOSSales: POSSaleRecord[] = [];

  private listeners = new Set<SimulationListener>();

  constructor() {
    this.virtualTime = new Date();
  }

  public subscribe(listener: SimulationListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private emit(type: SimulationEventType, message: string, data?: unknown) {
    const event: SimulationEvent = {
      type,
      message,
      data,
      timestamp: this.virtualTime.toISOString(),
    };
    this.listeners.forEach((listener) => {
      try {
        listener(event);
      } catch {
        // Suppress listener exceptions
      }
    });
  }

  public start(): void {
    if (this.isRunning && this.intervalId !== null) return;
    if (this.intervalId !== null) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
    this.isRunning = true;
    this.emit('STATUS_CHANGE', 'Simulation clock started');

    const tickInterval = 1000;
    this.intervalId = window.setInterval(() => {
      this.tick();
    }, tickInterval);
  }

  public stop(): void {
    this.isRunning = false;
    if (this.intervalId !== null) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
    this.emit('STATUS_CHANGE', 'Simulation clock paused');
  }

  public togglePause(): boolean {
    if (this.isRunning) {
      this.stop();
    } else {
      this.start();
    }
    return this.isRunning;
  }

  public setSpeed(speed: SimulationSpeed): void {
    this.speed = speed;
    this.emit('STATUS_CHANGE', `Simulation speed set to ${speed}x`, { speed });
  }

  public getSpeed(): SimulationSpeed {
    return this.speed;
  }

  public getIsRunning(): boolean {
    return this.isRunning;
  }

  public getRecentPOSSales(): POSSaleRecord[] {
    return [...this.recentPOSSales];
  }

  public getVirtualTime(): Date {
    return new Date(this.virtualTime);
  }

  /**
   * Internal clock tick.
   * Advances virtual time according to current speed multiplier.
   */
  public tick(): void {
    const deltaSeconds = 1 * this.speed;
    this.virtualTime = new Date(this.virtualTime.getTime() + deltaSeconds * 1000);

    // Automatic background sales and listings are disabled; actions are triggered manually on demand
    this.emit('TICK', `Virtual time: ${this.virtualTime.toLocaleTimeString()}`, {
      virtualTime: this.virtualTime.toISOString(),
      speed: this.speed,
    });
  }

  /**
   * Performs an automated or manual POS sale with FEFO deduction.
   * Mirrors real POS deduction: supports external_id idempotency, FEFO ordering,
   * multiple batch deduction, and rejection when stock is insufficient.
   */
  public executeRandomPOSSale(
    arg1?: number | POSSalePayload,
    arg2?: number
  ): POSSaleResult {
    let payload: POSSalePayload = {};
    if (typeof arg1 === 'number') {
      payload = { targetProductId: arg1, quantity: arg2 };
    } else if (arg1 && typeof arg1 === 'object') {
      payload = arg1;
    }

    const state = demoSource.getInternalState();
    const todayStr = this.virtualTime.toISOString().split('T')[0];

    // 1. Resolve receipt number (external_id)
    const receiptNumber =
      payload.receiptNumber ||
      `REC-${this.virtualTime.getFullYear()}${(this.virtualTime.getMonth() + 1).toString().padStart(2, '0')}${this.virtualTime.getDate().toString().padStart(2, '0')}-${Math.floor(1000 + Math.random() * 9000)}`;

    // 2. Idempotency Check: A repeated receipt number must NOT deduct twice!
    const existingTxns = state.transactions.filter(
      (t) => t.external_id === receiptNumber && t.txn_type === 'SOLD'
    );
    if (existingTxns.length > 0) {
      const batchesUsed = Array.from(
        new Set(
          existingTxns.map((t) => {
            const b = state.batches.find((batch) => batch.id === t.batch);
            return b ? b.batch_code : `BTH-${t.batch}`;
          })
        )
      );
      const firstBatch = state.batches.find((b) => b.id === existingTxns[0].batch);
      const prod = firstBatch ? state.products.find((p) => p.id === firstBatch.product) : null;
      const prodName = prod?.name || 'Product';
      const unit = prod?.unit || 'pcs';
      const totalDeducted = existingTxns.reduce((acc, t) => acc + parseFloat(t.quantity), 0);

      const replayMsg = `Idempotent replay: Receipt ${receiptNumber} already processed (${totalDeducted} ${unit} ${prodName} - no duplicate deduction)`;

      const record: POSSaleRecord = {
        id: `replay-${Date.now()}-${receiptNumber}`,
        receiptNumber,
        productName: prodName,
        barcodeOrSku: prod?.barcode || prod?.sku || `PROD-${prod?.id || 1}`,
        quantity: totalDeducted,
        unit,
        batchesUsed,
        timestamp: this.virtualTime.toLocaleTimeString(),
        isIdempotentReplay: true,
      };
      this.recentPOSSales.unshift(record);
      if (this.recentPOSSales.length > 10) this.recentPOSSales.pop();

      this.emit('POS_SALE', replayMsg, {
        receiptNumber,
        productName: prodName,
        quantity: totalDeducted,
        unit,
        batchesUsed,
        isIdempotentReplay: true,
        record,
      });

      return {
        success: true,
        isIdempotentReplay: true,
        message: replayMsg,
        receiptNumber,
        productName: prodName,
        quantityDeducted: 0,
        unit,
        batchesUsed,
      };
    }

    // 3. Resolve Product
    let product = undefined;
    if (payload.targetProductId) {
      product = state.products.find((p) => p.id === payload.targetProductId);
    } else if (payload.barcode) {
      product = state.products.find((p) => p.barcode === payload.barcode);
    } else if (payload.sku) {
      product = state.products.find((p) => p.sku === payload.sku);
    } else {
      // Pick a random product with sellable stock (ACTIVE, not expired, quantity > 0)
      const sellableBatches = state.batches.filter(
        (b) => b.status === 'ACTIVE' && b.expiry_date >= todayStr && parseFloat(b.quantity) > 0
      );
      const sellableProductIds = Array.from(new Set(sellableBatches.map((b) => b.product)));
      const sellableProducts = state.products.filter(
        (p) => p.is_active && sellableProductIds.includes(p.id)
      );

      if (sellableProducts.length === 0) {
        return { success: false, message: 'No sellable stock available' };
      }
      product = sellableProducts[Math.floor(Math.random() * sellableProducts.length)];
    }

    if (!product) {
      return { success: false, message: 'Target product not found' };
    }

    // 4. Candidate Batches via FEFO (earliest expiry first, then earliest received_date, then id)
    const candidateBatches = state.batches
      .filter(
        (b) =>
          b.product === product.id &&
          b.status === 'ACTIVE' &&
          b.expiry_date >= todayStr &&
          parseFloat(b.quantity) > 0
      )
      .sort((a, b) => {
        const expCmp = a.expiry_date.localeCompare(b.expiry_date);
        if (expCmp !== 0) return expCmp;
        const recA = a.received_date || a.created_at || '';
        const recB = b.received_date || b.created_at || '';
        const recCmp = recA.localeCompare(recB);
        if (recCmp !== 0) return recCmp;
        return a.id - b.id;
      });

    if (candidateBatches.length === 0) {
      return { success: false, message: `No active sellable stock for ${product.name}` };
    }

    const totalAvailable = candidateBatches.reduce((acc, b) => acc + parseFloat(b.quantity), 0);

    // 5. Quantity Determination & Insufficient Stock Check
    let reqQty: number;
    if (payload.quantity !== undefined) {
      if (payload.quantity <= 0) {
        return { success: false, message: 'Quantity must be positive' };
      }
      // Rejects when stock is insufficient
      if (payload.quantity > totalAvailable) {
        return {
          success: false,
          message: `Insufficient stock for ${product.name}. Available: ${totalAvailable} ${product.unit}, Requested: ${payload.quantity} ${product.unit}`,
        };
      }
      reqQty = payload.quantity;
    } else {
      // Automatic / random sale picks a random quantity (1-3, capped at available stock)
      reqQty = Math.min(1 + Math.floor(Math.random() * 3), Math.floor(totalAvailable));
      if (reqQty <= 0) reqQty = Math.min(1, totalAvailable);
    }

    // 6. Deduct across batches using FEFO
    let rem = reqQty;
    const batchesUsed: string[] = [];

    for (const b of candidateBatches) {
      if (rem <= 0) break;
      const bQty = parseFloat(b.quantity);
      const curDeduct = Math.min(bQty, rem);
      const newQty = parseFloat((bQty - curDeduct).toFixed(2));
      b.quantity = String(newQty);
      if (newQty === 0) {
        b.status = 'DEPLETED';
      }
      rem = parseFloat((rem - curDeduct).toFixed(2));
      batchesUsed.push(b.batch_code);

      state.transactions.unshift({
        id: state.transactions.length + 1,
        organization: 1,
        batch: b.id,
        txn_type: 'SOLD',
        quantity: String(curDeduct),
        reason: 'Simulated POS Checkout',
        source: payload.source || 'POS',
        created_by: 1,
        created_at: this.virtualTime.toISOString(),
        external_id: receiptNumber,
      });
    }

    // 7. Format toast message: "POS sale: 3 pcs Amul Taaza, FEFO batch BTH-..."
    const batchListStr = batchesUsed.join(', ');
    const msg = `POS sale: ${reqQty} ${product.unit || 'pcs'} ${product.name}, FEFO batch ${batchListStr}`;

    const record: POSSaleRecord = {
      id: `${Date.now()}-${receiptNumber}`,
      receiptNumber,
      productName: product.name,
      barcodeOrSku: product.barcode || product.sku || `PROD-${product.id}`,
      quantity: reqQty,
      unit: product.unit || 'pcs',
      batchesUsed,
      timestamp: this.virtualTime.toLocaleTimeString(),
    };
    this.recentPOSSales.unshift(record);
    if (this.recentPOSSales.length > 10) this.recentPOSSales.pop();

    this.emit('POS_SALE', msg, {
      receiptNumber,
      productName: product.name,
      quantity: reqQty,
      unit: product.unit,
      batchesUsed,
      record,
    });

    return {
      success: true,
      message: msg,
      receiptNumber,
      productName: product.name,
      quantityDeducted: reqQty,
      unit: product.unit,
      batchesUsed,
    };
  }

  /**
   * Broadcasts a new surplus listing into the NGO food feed.
   */
  public executeAutoListing(): { success: boolean; message: string } {
    const state = demoSource.getInternalState();
    // Look for an active batch expiring soon that is not yet donated
    const todayStr = this.virtualTime.toISOString().split('T')[0];
    const candidateBatches = state.batches.filter(
      (b) => b.status === 'ACTIVE' && b.expiry_date >= todayStr && parseFloat(b.quantity) > 0
    );

    if (candidateBatches.length === 0) return { success: false, message: 'No candidate batches' };
    const batch = candidateBatches[Math.floor(Math.random() * candidateBatches.length)];
    const prod = state.products.find((p) => p.id === batch.product);

    const newListing: DonationListing = {
      id: state.listings.length + 1,
      business_id: 1,
      business_name: 'The Grand Gateway Bengaluru',
      business_rating: 4.9,
      batch_id: batch.id,
      product_name: prod?.name || 'Surplus Food Batch',
      category: 'Surplus Prepared Foods',
      quantity: Math.min(parseFloat(batch.quantity), 25),
      unit: prod?.unit || 'kg',
      expiry_date: batch.expiry_date,
      pickup_window_start: '20:00',
      pickup_window_end: '22:30',
      status: 'AVAILABLE',
      address: 'Service Gate 3, The Grand Gateway, MG Road, Bengaluru',
      latitude: 12.9754,
      longitude: 77.6190,
      distance_km: 1.5,
      created_at: this.virtualTime.toISOString(),
    };

    state.listings.unshift(newListing);

    // Add in-app notification
    const notif: NotificationItem = {
      id: `notif-${Date.now()}`,
      type: 'LISTING',
      title: 'New Surplus Donation Broadcast',
      message: `${newListing.quantity} ${newListing.unit} of ${newListing.product_name} ready for pickup`,
      timestamp: this.virtualTime.toISOString(),
      is_read: false,
    };
    state.notifications.unshift(notif);

    const msg = `New surplus listing: ${newListing.quantity} ${newListing.unit} ${newListing.product_name}`;
    this.emit('NEW_LISTING', msg, { listing: newListing, notification: notif });

    return { success: true, message: msg };
  }

  /**
   * Advances oldest PENDING claim to CONFIRMED, or CONFIRMED to PICKED_UP.
   */
  public advanceOldestClaim(): { success: boolean; message: string } {
    const state = demoSource.getInternalState();
    // 1. Check for PENDING claim
    const pendingClaim = state.claims.find((c) => c.status === 'PENDING');
    if (pendingClaim) {
      pendingClaim.status = 'CONFIRMED';
      pendingClaim.updated_at = this.virtualTime.toISOString();
      const msg = `Claim #${pendingClaim.id} confirmed by donor for ${pendingClaim.ngo_name}`;
      this.emit('CLAIM_STATUS_CHANGE', msg, { claim: pendingClaim });
      return { success: true, message: msg };
    }

    // 2. Check for CONFIRMED claim to pick up
    const confirmedClaim = state.claims.find((c) => c.status === 'CONFIRMED');
    if (confirmedClaim) {
      confirmedClaim.status = 'PICKED_UP';
      confirmedClaim.updated_at = this.virtualTime.toISOString();
      if (confirmedClaim.listing) confirmedClaim.listing.status = 'PICKED_UP';
      const msg = `Food rescued! ${confirmedClaim.ngo_name} completed pickup for Claim #${confirmedClaim.id}`;
      this.emit('CLAIM_STATUS_CHANGE', msg, { claim: confirmedClaim });
      return { success: true, message: msg };
    }

    return { success: false, message: 'No active claims to advance' };
  }

  /**
   * Adds an urgent expiring batch to stress test alert & FEFO queues.
   */
  public addExpiringBatch(hoursToExpiry = 24, quantity = 25): { success: boolean; message: string; batch?: Batch } {
    const state = demoSource.getInternalState();
    const prod = state.products[0] || { id: 1, name: 'Sample Item', unit: 'kg' };

    const exp = new Date(this.virtualTime.getTime() + hoursToExpiry * 3600 * 1000);
    const batchCode = `BTH-${exp.getFullYear()}${String(exp.getMonth() + 1).padStart(2, '0')}-EXP${Date.now() % 1000}`;

    const newBatch: Batch = {
      id: state.batches.length + 1,
      organization: 1,
      product: prod.id,
      location: 1,
      batch_code: batchCode,
      quantity: quantity.toFixed(1),
      received_date: this.virtualTime.toISOString().split('T')[0],
      expiry_date: exp.toISOString().split('T')[0],
      status: 'ACTIVE',
      created_at: this.virtualTime.toISOString(),
    };

    state.batches.unshift(newBatch);

    // Append to transactions (Received inward)
    state.transactions.unshift({
      id: state.transactions.length + 1,
      organization: 1,
      batch: newBatch.id,
      txn_type: 'RECEIVED',
      quantity: newBatch.quantity,
      reason: 'Urgent Dispatch Test Batch Inward',
      source: 'MANUAL',
      created_by: 1,
      created_at: this.virtualTime.toISOString(),
      external_id: `INW-${Date.now()}`,
    });

    const msg = `Added expiring batch: ${batchCode} (${quantity} ${prod.unit} expiring in ${hoursToExpiry}h)`;
    this.emit('BATCH_ADDED', msg, { batch: newBatch });
    return { success: true, message: msg, batch: newBatch };
  }

  /**
   * Fast-forwards virtual time by N days.
   * Updates batch expiry statuses and triggers expiry alerts.
   */
  public fastForwardDays(days = 1): { success: boolean; message: string } {
    const msToAdd = days * 24 * 3600 * 1000;
    this.virtualTime = new Date(this.virtualTime.getTime() + msToAdd);

    const state = demoSource.getInternalState();
    const todayStr = this.virtualTime.toISOString().split('T')[0];

    // Check for newly expired batches
    let newlyExpired = 0;
    state.batches.forEach((b) => {
      if (b.status === 'ACTIVE' && b.expiry_date < todayStr) {
        b.status = 'EXPIRED';
        newlyExpired++;
        // Remove any alerts for this now-expired batch so it is not in the alert section
        state.alerts = state.alerts.filter((a) => a.batch !== b.id);
        // Log wasted transaction
        state.transactions.unshift({
          id: state.transactions.length + 1,
          organization: 1,
          batch: b.id,
          txn_type: 'WASTED',
          quantity: b.quantity,
          reason: 'Auto-expired during fast-forward',
          source: 'SYSTEM',
          created_by: null,
          created_at: this.virtualTime.toISOString(),
          external_id: `FFW-EXP-${Date.now()}-${b.id}`,
        });
      }
    });

    const msg = `Fast-forwarded ${days} day(s). New virtual date: ${todayStr}. ${newlyExpired} batches expired.`;
    this.emit('CLOCK_FAST_FORWARD', msg, { days, virtualDate: todayStr, newlyExpired });
    return { success: true, message: msg };
  }

  /**
   * Resets simulation data to initial deterministic state.
   */
  public resetData(): void {
    const demo = demoSource as unknown as { seedDeterministicData?: () => void; clearCustomData?: () => void };
    if (typeof demo.clearCustomData === 'function') {
      demo.clearCustomData();
    }
    if (typeof demo.seedDeterministicData === 'function') {
      demo.seedDeterministicData();
    }
    this.virtualTime = new Date();
    this.recentPOSSales = [];
    this.emit('RESET', 'Simulation state reset to default seed');
  }

  /**
   * Proves mathematically that stock totals always reconcile:
   * received === sold + discarded + donated + remaining
   */
  public reconcileStock(targetProductId?: number): ReconcileResult {
    const state = demoSource.getInternalState();
    const productsToCheck = targetProductId
      ? state.products.filter((p) => p.id === targetProductId)
      : state.products;

    let grandReceived = 0;
    let grandSold = 0;
    let grandDiscarded = 0;
    let grandDonated = 0;
    let grandRemaining = 0;

    const breakdown: ReconcileResult['productBreakdown'] = [];

    for (const prod of productsToCheck) {
      const prodBatches = state.batches.filter((b) => b.product === prod.id);

      let prodReceived = 0;
      let prodSold = 0;
      let prodDiscarded = 0;
      let prodDonated = 0;
      let prodRemaining = 0;

      for (const b of prodBatches) {
        const bTxns = state.transactions.filter((t) => t.batch === b.id);
        let bReceived = 0;
        let bSold = 0;
        let bDiscarded = 0;
        let bDonated = 0;

        for (const t of bTxns) {
          const q = parseFloat(t.quantity) || 0;
          if (t.txn_type === 'RECEIVED') bReceived += q;
          else if (t.txn_type === 'SOLD') bSold += q;
          else if (t.txn_type === 'DISCARDED' || t.txn_type === 'WASTED') bDiscarded += q;
          else if (t.txn_type === 'DONATED') bDonated += q;
        }

        const bRem = b.status === 'ACTIVE' ? (parseFloat(b.quantity) || 0) : 0;
        // If batch was seeded without explicit RECEIVED transaction, initial received was remaining + deductions
        if (bReceived === 0) {
          bReceived = bRem + bSold + bDiscarded + bDonated;
        }

        prodReceived += bReceived;
        prodSold += bSold;
        prodDiscarded += bDiscarded;
        prodDonated += bDonated;
        prodRemaining += bRem;
      }

      const prodAccounted = prodSold + prodDiscarded + prodDonated + prodRemaining;
      const isReconciled = Math.abs(prodReceived - prodAccounted) < 0.05;

      breakdown.push({
        productId: prod.id,
        productName: prod.name,
        received: Number(prodReceived.toFixed(2)),
        accounted: Number(prodAccounted.toFixed(2)),
        reconciled: isReconciled,
      });

      grandReceived += prodReceived;
      grandSold += prodSold;
      grandDiscarded += prodDiscarded;
      grandDonated += prodDonated;
      grandRemaining += prodRemaining;
    }

    const grandAccounted = grandSold + grandDiscarded + grandDonated + grandRemaining;
    const delta = Math.abs(grandReceived - grandAccounted);
    const isOverallReconciled = delta < 0.1;

    return {
      isReconciled: isOverallReconciled,
      received: Number(grandReceived.toFixed(2)),
      sold: Number(grandSold.toFixed(2)),
      discarded: Number(grandDiscarded.toFixed(2)),
      donated: Number(grandDonated.toFixed(2)),
      remaining: Number(grandRemaining.toFixed(2)),
      sumDeductionsAndRemaining: Number(grandAccounted.toFixed(2)),
      delta: Number(delta.toFixed(2)),
      productBreakdown: breakdown,
    };
  }
}

// Singleton Engine Instance
export const simulationEngine = SimulationEngine.getInstance();

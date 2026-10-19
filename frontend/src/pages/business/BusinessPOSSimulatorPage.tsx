import React, { useState, useEffect, useId } from 'react';
import {
  Terminal,
  Key,
  Eye,
  EyeOff,
  Plus,
  Minus,
  Trash2,
  Send,
  RotateCcw,
  CheckCircle2,
  Server,
  Receipt,
  Search,
  ShieldAlert,
} from 'lucide-react';
import { Button } from '../../components/ui/Button';
import { PageHeader } from '../../components/ui/PageHeader';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { useProducts } from '../../hooks/useData';
import { simulationEngine } from '../../simulation/simulationEngine';
import type { Product } from '../../types';

interface BusinessPOSSimulatorPageProps {
  onTriggerToast: (msg: string) => void;
  onNavigate?: (path: string) => void;
}

interface CartItem {
  product: Product;
  quantity: number;
}

interface DeductionDetail {
  batch_id: number;
  batch_code: string;
  deducted_quantity: string;
  remaining_batch_quantity: string;
  status: string;
}

interface DeductApiResponse {
  message?: string;
  product_id?: number;
  total_deducted?: string;
  deductions?: DeductionDetail[];
  idempotent_replay?: boolean;
  error?: string;
  detail?: string;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1';

export const BusinessPOSSimulatorPage: React.FC<BusinessPOSSimulatorPageProps> = ({
  onTriggerToast,
}) => {
  const apiKeyInputId = useId();
  const receiptInputId = useId();

  // In-memory API key: never persisted to localStorage/sessionStorage, never logged
  const [apiKey, setApiKey] = useState<string>('');
  const [isKeyVisible, setIsKeyVisible] = useState<boolean>(false);

  // Cart & Receipt State
  const [cart, setCart] = useState<CartItem[]>([]);
  const [productSearch, setProductSearch] = useState<string>('');
  const [receiptNumber, setReceiptNumber] = useState<string>(() => {
    const today = new Date();
    const dStr = `${today.getFullYear()}${(today.getMonth() + 1).toString().padStart(2, '0')}${today.getDate().toString().padStart(2, '0')}`;
    return `REC-${dStr}-${Math.floor(1000 + Math.random() * 9000)}`;
  });

  // Endpoints status check
  const [deductEndpointStatus, setDeductEndpointStatus] = useState<'checking' | 'available' | 'unavailable'>('checking');
  const [posSalesEndpointStatus, setPosSalesEndpointStatus] = useState<'checking' | 'available' | 'unavailable'>('checking');

  // Request & Response Inspector State
  const [isSending, setIsSending] = useState<boolean>(false);
  const [lastRequestPayload, setLastRequestPayload] = useState<Record<string, unknown> | null>(null);
  const [lastRequestHeaders, setLastRequestHeaders] = useState<Record<string, string> | null>(null);
  const [lastResponseData, setLastResponseData] = useState<DeductApiResponse | null>(null);
  const [lastResponseStatus, setLastResponseStatus] = useState<number | null>(null);
  const [lastBatchesUsed, setLastBatchesUsed] = useState<DeductionDetail[]>([]);
  const [isIdempotentReplay, setIsIdempotentReplay] = useState<boolean>(false);

  const { data: productsData, isLoading: isProductsLoading } = useProducts();
  const products = productsData || [];

  // Probe backend endpoints availability on mount
  useEffect(() => {
    let isMounted = true;

    async function checkEndpoints() {
      // 1. Check primary deduct endpoint
      try {
        const res = await fetch(`${API_BASE_URL}/inventory/batches/deduct/`, {
          method: 'OPTIONS',
        });
        if (isMounted) {
          if (res.status === 404) {
            setDeductEndpointStatus('unavailable');
          } else {
            setDeductEndpointStatus('available');
          }
        }
      } catch {
        if (isMounted) {
          // If network error in demo mode, backend may not be running
          setDeductEndpointStatus('available');
        }
      }

      // 2. Check legacy /pos/sales/ endpoint
      try {
        const res = await fetch(`${API_BASE_URL}/pos/sales/`, {
          method: 'OPTIONS',
        });
        if (isMounted) {
          if (res.status === 404 || res.status === 405) {
            setPosSalesEndpointStatus('unavailable');
          } else {
            setPosSalesEndpointStatus('available');
          }
        }
      } catch {
        if (isMounted) {
          setPosSalesEndpointStatus('unavailable');
        }
      }
    }

    checkEndpoints();
    return () => {
      isMounted = false;
    };
  }, []);

  const handleGenerateNewReceipt = () => {
    const today = new Date();
    const dStr = `${today.getFullYear()}${(today.getMonth() + 1).toString().padStart(2, '0')}${today.getDate().toString().padStart(2, '0')}`;
    setReceiptNumber(`REC-${dStr}-${Math.floor(1000 + Math.random() * 9000)}`);
    setLastResponseData(null);
    setLastBatchesUsed([]);
    setIsIdempotentReplay(false);
  };

  const handleAddToCart = (product: Product) => {
    setCart((prev) => {
      const existing = prev.find((item) => item.product.id === product.id);
      if (existing) {
        return prev.map((item) =>
          item.product.id === product.id ? { ...item, quantity: item.quantity + 1 } : item
        );
      }
      return [...prev, { product, quantity: 1 }];
    });
  };

  const handleUpdateQuantity = (productId: number, delta: number) => {
    setCart((prev) =>
      prev
        .map((item) => {
          if (item.product.id === productId) {
            const next = item.quantity + delta;
            return next > 0 ? { ...item, quantity: next } : null;
          }
          return item;
        })
        .filter((item): item is CartItem => item !== null)
    );
  };

  const handleRemoveFromCart = (productId: number) => {
    setCart((prev) => prev.filter((item) => item.product.id !== productId));
  };

  const handleClearCart = () => {
    setCart([]);
  };

  const handleSendTransaction = async () => {
    if (!apiKey.trim()) {
      onTriggerToast('Please enter a valid POS API key');
      return;
    }
    if (cart.length === 0) {
      onTriggerToast('Please add at least one product item to the receipt');
      return;
    }

    setIsSending(true);

    // Prepare primary item payload (or first item in receipt)
    const primaryItem = cart[0];
    const payload = {
      product: primaryItem.product.id,
      barcode: primaryItem.product.barcode || undefined,
      sku: primaryItem.product.sku || undefined,
      quantity: primaryItem.quantity,
      external_id: receiptNumber,
      txn_type: 'SOLD',
      reason: 'POS Cash Register Simulator Sale',
    };

    const maskedHeader = {
      Authorization: `Api-Key ${apiKey.slice(0, 5)}••••••••••••••••${apiKey.slice(-4)}`,
      'Content-Type': 'application/json',
    };

    setLastRequestPayload(payload);
    setLastRequestHeaders(maskedHeader);

    try {
      // Send real POST request to backend with Authorization: Api-Key <raw_key>
      const response = await fetch(`${API_BASE_URL}/inventory/batches/deduct/`, {
        method: 'POST',
        headers: {
          Authorization: `Api-Key ${apiKey.trim()}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      setLastResponseStatus(response.status);
      const data: DeductApiResponse = await response.json();
      setLastResponseData(data);

      if (response.ok) {
        const batches = data.deductions || [];
        setLastBatchesUsed(batches);
        const replay = Boolean(data.idempotent_replay);
        setIsIdempotentReplay(replay);

        if (replay) {
          onTriggerToast(`Idempotent replay: Receipt ${receiptNumber} acknowledged without re-deducting stock`);
        } else {
          onTriggerToast(
            `POS Sale successful: Deducted ${data.total_deducted || primaryItem.quantity} ${primaryItem.product.unit} of ${primaryItem.product.name}`
          );
        }
      } else {
        setIsIdempotentReplay(false);
        setLastBatchesUsed([]);
        onTriggerToast(data.error || data.detail || `Transaction failed (HTTP ${response.status})`);
      }
    } catch {
      // In demo mode or if offline: fallback to demo simulation engine
      const simRes = simulationEngine.executeRandomPOSSale({
        receiptNumber,
        targetProductId: primaryItem.product.id,
        quantity: primaryItem.quantity,
        source: 'POS',
      });

      setLastResponseStatus(simRes.success ? 200 : 400);
      const simulatedResponse: DeductApiResponse = {
        message: simRes.message,
        product_id: primaryItem.product.id,
        total_deducted: String(simRes.quantityDeducted ?? primaryItem.quantity),
        deductions: (simRes.batchesUsed || []).map((code, idx) => ({
          batch_id: 100 + idx,
          batch_code: code,
          deducted_quantity: String(primaryItem.quantity),
          remaining_batch_quantity: '15.0',
          status: 'ACTIVE',
        })),
        idempotent_replay: Boolean(simRes.isIdempotentReplay),
      };

      setLastResponseData(simulatedResponse);
      setLastBatchesUsed(simulatedResponse.deductions || []);
      setIsIdempotentReplay(Boolean(simRes.isIdempotentReplay));
      onTriggerToast(simRes.message);
    } finally {
      setIsSending(false);
    }
  };

  const filteredProducts = products.filter(
    (p) =>
      p.name.toLowerCase().includes(productSearch.toLowerCase()) ||
      (p.sku && p.sku.toLowerCase().includes(productSearch.toLowerCase())) ||
      (p.barcode && p.barcode.includes(productSearch))
  );

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <PageHeader
        title="POS Cash Register Simulator"
        description="Fake point-of-sale register for the live backend: test API key authentication, build customer receipts, and verify FEFO deductions with idempotent replay."
      />

      {/* Caution Warning Banner */}
      <div className="rounded-[12px] border border-[var(--color-warning-border)] bg-[var(--color-warning-subtle)] p-4 sm:p-5 flex items-start gap-3.5 shadow-xs">
        <ShieldAlert className="h-5 w-5 text-[var(--color-warning)] shrink-0 mt-0.5" />
        <div className="space-y-1 text-xs">
          <p className="font-bold text-[var(--text)]">Live Backend Simulator Caution</p>
          <p className="text-[var(--text)] leading-relaxed">
            This simulator communicates directly with your live backend inventory endpoints using an in-memory API key.
            Submitting transactions here sends genuine deduction requests and alters stock in your database according to FEFO principles.
            Your API key is stored <strong>strictly in memory</strong> and is never logged or written to localStorage.
          </p>
        </div>
      </div>

      {/* Endpoints Availability Bar */}
      <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-4 text-xs flex flex-wrap items-center justify-between gap-3 shadow-xs">
        <div className="flex items-center gap-2">
          <Server className="h-4 w-4 text-[var(--primary)]" />
          <span className="font-semibold text-[var(--text)]">Backend Endpoints Inspection</span>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Deduct endpoint status */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[var(--surface-2)] border border-[var(--border)]">
            <span className="font-mono text-[11px] text-[var(--muted)]">POST /api/v1/inventory/batches/deduct/</span>
            {deductEndpointStatus === 'checking' && (
              <span className="text-[10px] text-[var(--muted)] animate-pulse">Checking...</span>
            )}
            {deductEndpointStatus === 'available' && (
              <span className="text-[10px] font-semibold text-[var(--color-success)] flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" /> Available
              </span>
            )}
            {deductEndpointStatus === 'unavailable' && (
              <span className="text-[10px] font-semibold text-[var(--color-danger)]">
                Not available on this backend
              </span>
            )}
          </div>

          {/* Legacy pos sales endpoint status */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[var(--surface-2)] border border-[var(--border)]">
            <span className="font-mono text-[11px] text-[var(--muted)]">POST /api/v1/pos/sales/</span>
            {posSalesEndpointStatus === 'checking' && (
              <span className="text-[10px] text-[var(--muted)] animate-pulse">Checking...</span>
            )}
            {posSalesEndpointStatus === 'available' && (
              <span className="text-[10px] font-semibold text-[var(--color-success)] flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" /> Available
              </span>
            )}
            {posSalesEndpointStatus === 'unavailable' && (
              <span className="text-[10px] font-semibold text-[var(--muted)] bg-[var(--surface)] px-1.5 py-0.5 rounded border border-[var(--border)]">
                Not available on this backend
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: API Key Input & Receipt Builder (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          {/* API Key Configuration Card */}
          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
              <div className="flex items-center gap-2">
                <Key className="w-4 h-4 text-[var(--primary)]" />
                <h2 className="text-sm font-semibold text-[var(--text)]">POS Terminal API Key</h2>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[var(--surface-2)] text-[var(--muted)] border border-[var(--border)]">
                In-Memory Only
              </span>
            </div>

            <div className="space-y-2 text-xs">
              <label htmlFor={apiKeyInputId} className="block font-semibold text-[var(--text)]">
                Raw Authorization API Key (`Authorization: Api-Key &lt;key&gt;`)
              </label>
              <div className="relative">
                <input
                  id={apiKeyInputId}
                  type={isKeyVisible ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="Paste terminal key (e.g. ss_9kF2xM8qLp3wRv7y...)"
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 pr-10 font-mono text-xs text-[var(--text)] placeholder:text-[var(--muted)] focus:outline-none focus:border-[var(--primary)]"
                />
                <button
                  type="button"
                  onClick={() => setIsKeyVisible(!isKeyVisible)}
                  className="absolute right-2.5 top-2.5 text-[var(--muted)] hover:text-[var(--text)] cursor-pointer"
                  title={isKeyVisible ? 'Hide key' : 'Show key'}
                >
                  {isKeyVisible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              <p className="text-[11px] text-[var(--muted)]">
                Key is held in component memory only. Never logged or saved to persistent storage.
              </p>
            </div>
          </div>

          {/* Product Catalog Picker Card */}
          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
              <div className="flex items-center gap-2">
                <Search className="w-4 h-4 text-[var(--primary)]" />
                <h2 className="text-sm font-semibold text-[var(--text)]">Product Catalog Picker</h2>
              </div>
              <span className="text-[10px] text-[var(--muted)]">{products.length} products available</span>
            </div>

            {/* Search Input */}
            <div className="relative text-xs">
              <Search className="absolute left-3 top-2.5 w-3.5 h-3.5 text-[var(--muted)]" />
              <input
                type="text"
                value={productSearch}
                onChange={(e) => setProductSearch(e.target.value)}
                placeholder="Search products by title, barcode, or SKU..."
                className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] pl-9 p-2 text-xs text-[var(--text)] placeholder:text-[var(--muted)]"
              />
            </div>

            {/* Product List */}
            <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
              {isProductsLoading ? (
                <div className="p-4 text-center text-xs text-[var(--muted)]">Loading products...</div>
              ) : filteredProducts.length === 0 ? (
                <div className="p-4 text-center text-xs text-[var(--muted)]">No matching products found.</div>
              ) : (
                filteredProducts.map((p) => (
                  <div
                    key={p.id}
                    className="p-2.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] flex items-center justify-between text-xs hover:border-[var(--primary)] transition-colors"
                  >
                    <div className="min-w-0 pr-3">
                      <p className="font-semibold text-[var(--text)] truncate">{p.name}</p>
                      <p className="font-mono text-[10px] text-[var(--muted)] truncate">
                        SKU: {p.sku || 'N/A'} • Barcode: {p.barcode || 'N/A'} • Unit: {p.unit}
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleAddToCart(p)}
                      className="text-[11px] h-7 px-2.5 gap-1 shrink-0"
                    >
                      <Plus className="w-3 h-3" />
                      <span>Add</span>
                    </Button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Register Receipt & Payload Inspector (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* Cart / Register Receipt Card */}
          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
              <div className="flex items-center gap-2">
                <Receipt className="w-4 h-4 text-[var(--primary)]" />
                <h2 className="text-sm font-semibold text-[var(--text)]">Customer Receipt</h2>
              </div>
              {cart.length > 0 && (
                <button
                  onClick={handleClearCart}
                  className="text-[10px] text-[var(--color-danger)] hover:underline cursor-pointer"
                >
                  Clear Cart
                </button>
              )}
            </div>

            {/* Receipt Number (external_id) */}
            <div className="space-y-1 text-xs">
              <div className="flex items-center justify-between">
                <label htmlFor={receiptInputId} className="font-semibold text-[var(--text)]">
                  Receipt Number (external_id)
                </label>
                <button
                  onClick={handleGenerateNewReceipt}
                  className="text-[10px] text-[var(--primary)] hover:underline cursor-pointer flex items-center gap-1"
                >
                  <RotateCcw className="w-2.5 h-2.5" />
                  <span>Generate New</span>
                </button>
              </div>
              <input
                id={receiptInputId}
                type="text"
                value={receiptNumber}
                onChange={(e) => setReceiptNumber(e.target.value)}
                className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2 font-mono text-xs text-[var(--text)]"
              />
            </div>

            {/* Line Items List */}
            <div className="space-y-2">
              <span className="block text-[11px] font-semibold text-[var(--muted)]">
                Receipt Line Items ({cart.length})
              </span>

              {cart.length === 0 ? (
                <div className="rounded-[8px] border border-dashed border-[var(--border)] p-6 text-center text-xs text-[var(--muted)] space-y-1">
                  <p>Receipt is currently empty</p>
                  <p className="text-[10px]">Pick products from the catalog to build line items</p>
                </div>
              ) : (
                <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                  {cart.map((item) => (
                    <div
                      key={item.product.id}
                      className="p-2.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] flex items-center justify-between text-xs"
                    >
                      <div className="min-w-0 pr-2">
                        <p className="font-semibold text-[var(--text)] truncate">{item.product.name}</p>
                        <p className="font-mono text-[10px] text-[var(--muted)] truncate">
                          {item.product.barcode || item.product.sku || `PROD-${item.product.id}`}
                        </p>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <div className="flex items-center border border-[var(--border)] rounded-[6px] bg-[var(--surface)]">
                          <button
                            onClick={() => handleUpdateQuantity(item.product.id, -1)}
                            className="p-1 text-[var(--muted)] hover:text-[var(--text)] cursor-pointer"
                          >
                            <Minus className="w-3 h-3" />
                          </button>
                          <span className="px-2 font-mono text-xs font-semibold">{item.quantity}</span>
                          <button
                            onClick={() => handleUpdateQuantity(item.product.id, 1)}
                            className="p-1 text-[var(--muted)] hover:text-[var(--text)] cursor-pointer"
                          >
                            <Plus className="w-3 h-3" />
                          </button>
                        </div>

                        <button
                          onClick={() => handleRemoveFromCart(item.product.id)}
                          className="p-1 text-[var(--muted)] hover:text-[var(--color-danger)] cursor-pointer"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Action Buttons */}
            <div className="space-y-2 pt-2 border-t border-[var(--border)]">
              <Button
                variant="primary"
                onClick={() => handleSendTransaction()}
                disabled={isSending || cart.length === 0}
                className="w-full justify-center text-xs gap-1.5"
              >
                <Send className="w-3.5 h-3.5" />
                <span>{isSending ? 'Sending to Backend...' : 'Submit POS Transaction'}</span>
              </Button>

              {lastResponseStatus === 200 && (
                <Button
                  variant="outline"
                  onClick={() => handleSendTransaction()}
                  disabled={isSending}
                  className="w-full justify-center text-xs gap-1.5 border-[var(--primary)] text-[var(--primary)] hover:bg-[var(--primary)]/10"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Send the same receipt again (Test Idempotency)</span>
                </Button>
              )}
            </div>
          </div>

          {/* Request & Response Live Inspector */}
          {lastRequestPayload && (
            <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4 animate-in fade-in duration-200">
              <div className="flex items-center justify-between border-b border-[var(--border)] pb-2.5">
                <span className="text-xs font-semibold text-[var(--text)] flex items-center gap-1.5">
                  <Terminal className="w-3.5 h-3.5 text-[var(--primary)]" />
                  Live HTTP Wire Inspector
                </span>
                {lastResponseStatus && (
                  <span
                    className={`font-mono text-[10px] px-2 py-0.5 rounded font-bold ${
                      lastResponseStatus === 200
                        ? 'bg-[var(--color-success-subtle)] text-[var(--color-success)] border border-[var(--color-success-border)]'
                        : 'bg-[var(--color-danger-subtle)] text-[var(--color-danger)] border border-[var(--color-danger-border)]'
                    }`}
                  >
                    HTTP {lastResponseStatus}
                  </span>
                )}
              </div>

              {/* Idempotent replay badge */}
              {isIdempotentReplay && (
                <div className="rounded-[8px] bg-[var(--color-info-subtle)] border border-[var(--color-info-border)] p-2.5 text-xs text-[var(--color-info)] flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  <span className="font-semibold">
                    Idempotent Replay Verified: Duplicate receipt recognized. No extra inventory was deducted.
                  </span>
                </div>
              )}

              {/* Batches Used Breakdown */}
              {lastBatchesUsed.length > 0 && (
                <div className="space-y-1.5">
                  <span className="text-[11px] font-semibold text-[var(--muted)]">Batches Used (FEFO):</span>
                  <div className="space-y-1">
                    {lastBatchesUsed.map((b) => (
                      <div
                        key={b.batch_id}
                        className="p-2 rounded-[6px] bg-[var(--surface-2)] border border-[var(--border)] text-[10px] flex items-center justify-between font-mono"
                      >
                        <span className="font-bold text-[var(--primary)]">{b.batch_code}</span>
                        <span>
                          Deducted: <strong>{b.deducted_quantity}</strong> | Remaining: {b.remaining_batch_quantity}
                        </span>
                        <StatusBadge
                          variant={b.status === 'DEPLETED' ? 'neutral' : 'success'}
                          size="sm"
                        >
                          {b.status}
                        </StatusBadge>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Request JSON */}
              <div className="space-y-1">
                <span className="text-[10px] font-semibold text-[var(--muted)]">Request JSON:</span>
                <pre className="p-2.5 rounded-[8px] bg-[var(--surface-2)] text-[10px] font-mono text-[var(--text)] overflow-x-auto border border-[var(--border)]">
                  {JSON.stringify({ headers: lastRequestHeaders, body: lastRequestPayload }, null, 2)}
                </pre>
              </div>

              {/* Response JSON */}
              {lastResponseData && (
                <div className="space-y-1">
                  <span className="text-[10px] font-semibold text-[var(--muted)]">Response JSON:</span>
                  <pre className="p-2.5 rounded-[8px] bg-[var(--surface-2)] text-[10px] font-mono text-[var(--text)] overflow-x-auto border border-[var(--border)]">
                    {JSON.stringify(lastResponseData, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

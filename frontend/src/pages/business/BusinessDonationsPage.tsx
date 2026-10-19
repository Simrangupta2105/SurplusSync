import React, { useState } from 'react';
import {
  HeartHandshake,
  Plus,
  Clock,
  CheckCircle2,
  Package,
  Building2,
  ShieldCheck,
} from 'lucide-react';
import { Button } from '../../components/ui/Button';
import { PageHeader } from '../../components/ui/PageHeader';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { ExpiryPill } from '../../components/ui/ExpiryPill';
import { Sheet } from '../../components/ui/Sheet';
import { FeatureGuard } from '../../components/FeatureGuard';
import {
  useDonationListings,
  useDonationClaims,
  useBatches,
  useCreateListing,
  useUpdateClaimStatus,
} from '../../hooks/useData';
import type { DonationListing, DonationClaim, BatchWithProduct } from '../../types';

interface BusinessDonationsPageProps {
  onTriggerToast: (msg: string) => void;
  onNavigate?: (path: string) => void;
}

export const BusinessDonationsPage: React.FC<BusinessDonationsPageProps> = ({
  onTriggerToast,
  onNavigate: _onNavigate,
}) => {
  const [activeTab, setActiveTab] = useState<'listings' | 'claims'>('listings');
  const [isListingSheetOpen, setIsListingSheetOpen] = useState(false);
  const [selectedBatchId, setSelectedBatchId] = useState<number>(1);
  const [windowHours, setWindowHours] = useState<number>(4);

  const { data: listings, isLoading: isListingsLoading } = useDonationListings();
  const { data: claims, isLoading: isClaimsLoading } = useDonationClaims();
  const { data: batches } = useBatches();
  const createListingMutation = useCreateListing();
  const updateClaimMutation = useUpdateClaimStatus();

  const handleCreateListing = (e: React.FormEvent) => {
    e.preventDefault();
    createListingMutation.mutate(
      { batchId: Number(selectedBatchId), windowHours: Number(windowHours) },
      {
        onSuccess: (_res) => {
          setIsListingSheetOpen(false);
          onTriggerToast('Surplus batch broadcasted to registered NGO feed');
        },
        onError: (err: unknown) => {
          const msg = err instanceof Error ? err.message : 'Unable to create donation listing';
          onTriggerToast(msg);
        },
      }
    );
  };

  const handleClaimAction = (claimId: number, status: 'CONFIRMED' | 'CANCELLED') => {
    updateClaimMutation.mutate(
      { claimId, status },
      {
        onSuccess: () => {
          onTriggerToast(`Claim #${claimId} marked as ${status}`);
        },
      }
    );
  };

  return (
    <FeatureGuard feature="marketplace_listings" featureName="Donations &amp; Food Rescue">
      <div className="space-y-6 animate-in fade-in duration-200">
        <PageHeader
          title="Donation Listings &amp; Claims"
          description="Broadcast expiring perishable stock batches to verified NGO feeding networks and coordinate volunteer pickup windows."
          action={
            <Button
              variant="primary"
              size="sm"
              onClick={() => setIsListingSheetOpen(true)}
              className="gap-1.5"
            >
              <Plus className="w-4 h-4" />
              <span>Broadcast Surplus Batch</span>
            </Button>
          }
        />

        {/* Tab Controls */}
        <div className="flex items-center gap-2 border-b border-[var(--border)] pb-3">
          <button
            type="button"
            onClick={() => setActiveTab('listings')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-[6px] text-xs font-semibold transition-all ${
              activeTab === 'listings'
                ? 'bg-[var(--surface-2)] text-[var(--text)] border border-[var(--border)] shadow-xs'
                : 'text-[var(--muted)] hover:text-[var(--text)]'
            }`}
          >
            <Package className="w-3.5 h-3.5 text-[var(--primary)]" />
            <span>Active Listings ({listings?.length || 0})</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('claims')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-[6px] text-xs font-semibold transition-all ${
              activeTab === 'claims'
                ? 'bg-[var(--surface-2)] text-[var(--text)] border border-[var(--border)] shadow-xs'
                : 'text-[var(--muted)] hover:text-[var(--text)]'
            }`}
          >
            <HeartHandshake className="w-3.5 h-3.5 text-[var(--accent)]" />
            <span>Incoming Claims ({claims?.length || 0})</span>
          </button>
        </div>

        {/* Tab 1: Active Listings */}
        {activeTab === 'listings' && (
          <div className="space-y-4">
            {isListingsLoading ? (
              <div className="space-y-3">
                <div className="h-20 rounded-[10px] bg-[var(--surface)] border border-[var(--border)] animate-pulse" />
                <div className="h-20 rounded-[10px] bg-[var(--surface)] border border-[var(--border)] animate-pulse" />
              </div>
            ) : listings?.length === 0 ? (
              <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-12 text-center space-y-3">
                <Package className="w-10 h-10 text-[var(--muted)] mx-auto opacity-50" />
                <h3 className="text-sm font-semibold text-[var(--text)]">No Active Donation Listings</h3>
                <p className="text-xs text-[var(--muted)] max-w-sm mx-auto">
                  When batches near their 48-hour shelf-life horizon, broadcast them directly to verified NGOs here.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {(listings || []).map((l: DonationListing) => (
                  <div
                    key={l.id}
                    className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 space-y-3.5 shadow-xs hover:border-[var(--primary)]/40 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h4 className="text-sm font-bold text-[var(--text)] truncate">{l.product_name}</h4>
                        <p className="text-xs text-[var(--muted)]">{l.category}</p>
                      </div>
                      <StatusBadge
                        status={l.status}
                        variant={
                          l.status === 'AVAILABLE'
                            ? 'success'
                            : l.status === 'CLAIMED'
                            ? 'warning'
                            : 'neutral'
                        }
                      >
                        {l.status}
                      </StatusBadge>
                    </div>

                    <div className="space-y-2 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="text-[var(--muted)]">Surplus Quantity:</span>
                        <span className="tabular-nums font-semibold text-[var(--text)]">
                          {l.quantity} {l.unit}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-[var(--muted)]">Expiry Horizon:</span>
                        <ExpiryPill expiryDate={l.expiry_date} />
                      </div>
                      <div className="flex items-center justify-between text-[11px] pt-1 border-t border-[var(--border)]/60">
                        <span className="text-[var(--muted)]">Pickup Closes:</span>
                        <span className="font-mono text-[var(--accent)] font-semibold">
                          {l.pickup_window_end}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Incoming Claims */}
        {activeTab === 'claims' && (
          <div className="space-y-4">
            {isClaimsLoading ? (
              <div className="space-y-3">
                <div className="h-20 rounded-[10px] bg-[var(--surface)] border border-[var(--border)] animate-pulse" />
              </div>
            ) : claims?.length === 0 ? (
              <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-12 text-center space-y-3">
                <HeartHandshake className="w-10 h-10 text-[var(--muted)] mx-auto opacity-50" />
                <h3 className="text-sm font-semibold text-[var(--text)]">No Claims Pending</h3>
                <p className="text-xs text-[var(--muted)] max-w-sm mx-auto">
                  When an NGO claims one of your listings, their pickup vehicle details and scheduled ETA will appear here for staff confirmation.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {(claims || []).map((c: DonationClaim) => (
                  <div
                    key={c.id}
                    className="p-5 rounded-[12px] border border-[var(--border)] bg-[var(--surface)] flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-xs"
                  >
                    <div className="space-y-1.5 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <StatusBadge
                          status={c.status}
                          variant={
                            c.status === 'CONFIRMED' || c.status === 'PICKED_UP'
                              ? 'success'
                              : c.status === 'PENDING'
                              ? 'warning'
                              : 'danger'
                          }
                        >
                          {c.status}
                        </StatusBadge>
                        <span className="font-semibold text-sm text-[var(--text)]">
                          {c.listing?.product_name || `Listing #${c.listing_id}`}
                          {c.listing ? ` (${c.listing.quantity} ${c.listing.unit})` : ''}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-[var(--muted)]">
                        <span className="flex items-center gap-1">
                          <Building2 className="w-3.5 h-3.5 text-[var(--primary)]" />
                          <strong className="text-[var(--text)]">{c.ngo_name}</strong>
                        </span>
                        <span>•</span>
                        <span className="flex items-center gap-1">
                          <Clock className="w-3.5 h-3.5" />
                          <span>Estimated Arrival: <strong className="text-[var(--text)]">{c.pickup_eta}</strong></span>
                        </span>
                      </div>
                      {c.notes && (
                        <p className="text-xs text-[var(--muted)] italic">
                          &quot;{c.notes}&quot;
                        </p>
                      )}
                    </div>

                    {/* Claim Actions */}
                    <div className="flex items-center gap-2 shrink-0">
                      {c.status === 'PENDING' ? (
                        <>
                          <Button
                            variant="primary"
                            size="sm"
                            disabled={updateClaimMutation.isPending}
                            onClick={() => handleClaimAction(c.id, 'CONFIRMED')}
                            className="gap-1.5 text-xs h-8 px-3"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Confirm Pickup</span>
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={updateClaimMutation.isPending}
                            onClick={() => handleClaimAction(c.id, 'CANCELLED')}
                            className="text-xs text-[var(--color-danger)] h-8 px-3"
                          >
                            Decline
                          </Button>
                        </>
                      ) : (
                        <span className="text-xs font-semibold text-[var(--muted)]">
                          Claim status locked
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Create Listing Sheet */}
        <Sheet
          isOpen={isListingSheetOpen}
          onClose={() => setIsListingSheetOpen(false)}
          title="Broadcast Surplus Batch"
          description="Select an expiring batch to list for verified NGO relief networks"
        >
          <form onSubmit={handleCreateListing} className="space-y-4 text-xs">
            <div>
              <label className="block font-semibold text-[var(--text)] mb-1">
                Select Active Batch
              </label>
              <select
                value={selectedBatchId}
                onChange={(e) => setSelectedBatchId(Number(e.target.value))}
                className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-[var(--text)]"
              >
                {(batches || []).map((b: BatchWithProduct) => (
                  <option key={b.id} value={b.id}>
                    {b.product_name} ({b.batch_code}) • {b.quantity} {b.unit} • Expires {b.expiry_date}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block font-semibold text-[var(--text)] mb-1">
                Pickup Window Horizon (Hours)
              </label>
              <select
                value={windowHours}
                onChange={(e) => setWindowHours(Number(e.target.value))}
                className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-[var(--text)]"
              >
                <option value={2}>2 Hours (Immediate Rescue)</option>
                <option value={4}>4 Hours (Standard Distribution)</option>
                <option value={8}>8 Hours (Extended Window)</option>
                <option value={24}>24 Hours (Next Day Horizon)</option>
              </select>
            </div>

            <div className="rounded-[8px] bg-[var(--surface-2)] p-3 text-[11px] text-[var(--muted)] space-y-1 border border-[var(--border)]">
              <span className="font-semibold text-[var(--text)] flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-[var(--primary)]" />
                Verified Relief Network Dispatch
              </span>
              <p>
                Listings will immediately appear on the verified NGO Food Feed with GPS coordinates of your facility.
              </p>
            </div>

            <div className="pt-4 flex items-center justify-end gap-2.5 border-t border-[var(--border)]">
              <Button
                variant="outline"
                size="sm"
                type="button"
                onClick={() => setIsListingSheetOpen(false)}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                type="submit"
                disabled={createListingMutation.isPending}
              >
                Broadcast Batch
              </Button>
            </div>
          </form>
        </Sheet>
      </div>
    </FeatureGuard>
  );
};

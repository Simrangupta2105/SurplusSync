import React, { useState } from 'react';
import {
  Clock,
  CheckCircle2,
  Building2,
  Star,
  MapPin,
  Truck,
  Filter,
  CheckCheck,
  Package,
} from 'lucide-react';
import { Button } from '../../components/ui/Button';
import { PageHeader } from '../../components/ui/PageHeader';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { RatingStars } from '../../components/ui/RatingStars';
import { FeatureGuard } from '../../components/FeatureGuard';
import {
  useDonationClaims,
  useUpdateClaimStatus,
  useRateClaim,
} from '../../hooks/useData';
import type { DonationClaim, ClaimStatus } from '../../types';

interface NgoClaimsPageProps {
  onTriggerToast: (msg: string) => void;
  onNavigate?: (path: string) => void;
}

export const NgoClaimsPage: React.FC<NgoClaimsPageProps> = ({
  onTriggerToast,
  onNavigate,
}) => {
  const [statusFilter, setStatusFilter] = useState<'ALL' | ClaimStatus>('ALL');
  const [ratingModalClaim, setRatingModalClaim] = useState<DonationClaim | null>(null);
  const [starRating, setStarRating] = useState<number>(5);
  const [feedbackText, setFeedbackText] = useState<string>('Punctual handover, packaging properly sealed and cold chain intact.');

  const { data: claims, isLoading } = useDonationClaims();
  const updateClaimMutation = useUpdateClaimStatus();
  const rateClaimMutation = useRateClaim();

  const filteredClaims = (claims || []).filter((c) => {
    if (statusFilter === 'ALL') return true;
    return c.status === statusFilter;
  });

  // Handle Mark Picked Up
  const handleMarkPickedUp = (claimId: number, productName: string) => {
    updateClaimMutation.mutate(
      { claimId, status: 'PICKED_UP' },
      {
        onSuccess: () => {
          onTriggerToast(`Marked rescue pickup completed for ${productName}!`);
        },
        onError: (err: unknown) => {
          const msg = err instanceof Error ? err.message : 'Failed to update claim status';
          onTriggerToast(msg);
        },
      }
    );
  };

  // Handle Submit Rating
  const handleSubmitRating = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ratingModalClaim) return;

    if (starRating < 1 || starRating > 5) {
      onTriggerToast('Please select between 1 and 5 stars.');
      return;
    }

    rateClaimMutation.mutate(
      {
        claimId: ratingModalClaim.id,
        payload: {
          stars: starRating,
          comment: feedbackText.trim(),
        },
      },
      {
        onSuccess: () => {
          const donorName = ratingModalClaim.listing?.business_name || 'Donor Partner';
          setRatingModalClaim(null);
          onTriggerToast(`Submitted ${starRating}-star feedback for ${donorName}!`);
        },
        onError: (err: unknown) => {
          const msg = err instanceof Error ? err.message : 'Unable to submit donor review';
          onTriggerToast(msg);
        },
      }
    );
  };

  return (
    <FeatureGuard feature="ngo_claims" featureName="My Claims & Rescue Logistics">
      <div className="space-y-6 animate-in fade-in duration-200">
        {/* Header */}
        <PageHeader
          title="My Rescue Claims"
          description="Track incoming donor approvals, volunteer dispatch schedules, and delivery milestones."
          action={
            onNavigate && (
              <Button
                variant="primary"
                size="sm"
                onClick={() => onNavigate('feed')}
                className="gap-1.5 text-xs font-semibold shadow-xs"
              >
                <Package className="w-4 h-4" />
                <span>Browse Live Feed</span>
              </Button>
            )
          }
        />

        {/* Filter Bar */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 p-3 rounded-[12px] bg-[var(--surface)] border border-[var(--border)]">
          <span className="text-xs text-[var(--muted)] font-medium mr-2 flex items-center gap-1">
            <Filter className="w-3.5 h-3.5" />
            <span>Filter Status:</span>
          </span>
          {[
            { label: 'All Dispatches', value: 'ALL' },
            { label: 'Pending Approval', value: 'PENDING' },
            { label: 'Confirmed & Ready', value: 'CONFIRMED' },
            { label: 'Completed Rescues', value: 'PICKED_UP' },
          ].map((chip) => (
            <button
              key={chip.label}
              type="button"
              onClick={() => setStatusFilter(chip.value as 'ALL' | ClaimStatus)}
              className={`px-3 py-1.5 rounded-[6px] text-xs font-semibold border transition-all shrink-0 ${
                statusFilter === chip.value
                  ? 'bg-[var(--primary)] text-white border-[var(--primary)] shadow-xs'
                  : 'bg-[var(--surface-2)] text-[var(--muted)] border-[var(--border)] hover:text-[var(--text)]'
              }`}
            >
              {chip.label}
            </button>
          ))}
        </div>

        {/* Claims List */}
        {isLoading ? (
          <div className="space-y-4">
            {[1, 2, 3].map((n) => (
              <div key={n} className="h-40 rounded-[12px] bg-[var(--surface-2)] animate-pulse" />
            ))}
          </div>
        ) : filteredClaims.length === 0 ? (
          <div className="py-16 text-center rounded-[12px] border border-[var(--border)] bg-[var(--surface)] space-y-3">
            <Clock className="w-10 h-10 text-[var(--muted)] mx-auto opacity-50" />
            <div className="space-y-1">
              <h4 className="text-sm font-semibold text-[var(--text)]">No Claims Found</h4>
              <p className="text-xs text-[var(--muted)] max-w-sm mx-auto">
                {statusFilter === 'ALL'
                  ? 'You have not claimed any surplus donations yet. Check the live feed to schedule your first pickup.'
                  : `No dispatches match the "${statusFilter}" filter status.`}
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredClaims.map((claim: DonationClaim) => {
              const productName = claim.listing?.product_name || `Listing #${claim.listing_id}`;
              const businessName = claim.listing?.business_name || 'Donor Facility';
              const quantity = claim.listing ? `${claim.listing.quantity} ${claim.listing.unit}` : 'Food Batch';

              return (
                <div
                  key={claim.id}
                  className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 shadow-xs space-y-5"
                >
                  {/* Top Bar: Product, Donor, Status Badge */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <StatusBadge
                          variant={
                            claim.status === 'PICKED_UP'
                              ? 'success'
                              : claim.status === 'CONFIRMED'
                              ? 'info'
                              : 'warning'
                          }
                          size="md"
                          dot
                        >
                          {claim.status}
                        </StatusBadge>
                        <h4 className="text-base font-bold text-[var(--text)]">
                          {productName}
                        </h4>
                        <span className="text-xs font-semibold tabular-nums text-[var(--primary)]">
                          ({quantity})
                        </span>
                      </div>
                      <div className="flex items-center flex-wrap gap-2 sm:gap-3 text-xs text-[var(--muted)]">
                        <span className="flex items-center gap-1 font-medium text-[var(--text)]">
                          <Building2 className="w-3.5 h-3.5 text-[var(--primary)]" />
                          <span>{businessName}</span>
                        </span>
                        {claim.listing?.business_rating && (
                          <>
                            <span>•</span>
                            <div className="flex items-center gap-1">
                              <RatingStars
                                value={claim.listing.business_rating}
                                size="sm"
                                showNumber
                                readOnly
                              />
                              {claim.listing.business_rating_count !== undefined && (
                                <span className="text-[10px] text-[var(--muted)] tabular-nums">
                                  ({claim.listing.business_rating_count})
                                </span>
                              )}
                            </div>
                          </>
                        )}
                        <span>•</span>
                        <span className="flex items-center gap-1">
                          <Clock className="w-3.5 h-3.5" />
                          <span>ETA: <strong className="text-[var(--text)]">{claim.pickup_eta}</strong></span>
                        </span>
                      </div>
                    </div>

                    {/* Actions based on state */}
                    <div className="flex items-center gap-2 self-start sm:self-auto shrink-0">
                      {claim.status === 'CONFIRMED' && (
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => handleMarkPickedUp(claim.id, productName)}
                          disabled={updateClaimMutation.isPending}
                          className="gap-1.5 text-xs font-semibold"
                        >
                          <CheckCheck className="w-4 h-4" />
                          <span>Mark as Picked Up</span>
                        </Button>
                      )}

                      {claim.status === 'PICKED_UP' && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setRatingModalClaim(claim);
                            setStarRating(claim.donor_rating || 5);
                            setFeedbackText(claim.donor_feedback || 'Punctual handover, packaging properly sealed and cold chain intact.');
                          }}
                          className="gap-1.5 text-xs text-[var(--color-warning)] border-[var(--color-warning-border)] hover:bg-[var(--color-warning-subtle)]"
                        >
                          <Star className="w-3.5 h-3.5 fill-[var(--color-warning)] text-[var(--color-warning)]" />
                          <span>{claim.donor_rating ? `Rated (${claim.donor_rating}★)` : 'Rate this Donor'}</span>
                        </Button>
                      )}
                    </div>
                  </div>

                  {/* Visual Status Timeline */}
                  <div className="p-4 rounded-[10px] bg-[var(--surface-2)] border border-[var(--border)]">
                    <div className="grid grid-cols-3 gap-2 text-center relative">
                      {/* Timeline Bar Background */}
                      <div className="absolute top-3.5 left-1/6 right-1/6 h-0.5 bg-[var(--border)] -z-0" />

                      {/* Step 1: Claim Submitted */}
                      <div className="flex flex-col items-center space-y-1.5 relative z-10">
                        <div className="w-7 h-7 rounded-full bg-[var(--color-success)] text-white flex items-center justify-center shadow-xs">
                          <CheckCircle2 className="w-4 h-4" />
                        </div>
                        <span className="text-xs font-semibold text-[var(--text)]">
                          1. Claim Sent
                        </span>
                        <span className="text-[10px] text-[var(--muted)]">Waiting verification</span>
                      </div>

                      {/* Step 2: Confirmed by Donor */}
                      <div className="flex flex-col items-center space-y-1.5 relative z-10">
                        <div
                          className={`w-7 h-7 rounded-full flex items-center justify-center transition-colors ${
                            claim.status === 'CONFIRMED' || claim.status === 'PICKED_UP'
                              ? 'bg-[var(--color-success)] text-white'
                              : 'bg-[var(--surface)] border border-[var(--border)] text-[var(--muted)]'
                          }`}
                        >
                          <Building2 className="w-3.5 h-3.5" />
                        </div>
                        <span
                          className={`text-xs font-semibold ${
                            claim.status === 'CONFIRMED' || claim.status === 'PICKED_UP'
                              ? 'text-[var(--text)]'
                              : 'text-[var(--muted)]'
                          }`}
                        >
                          2. Donor Confirmed
                        </span>
                        <span className="text-[10px] text-[var(--muted)]">Ready for pickup</span>
                      </div>

                      {/* Step 3: Picked Up */}
                      <div className="flex flex-col items-center space-y-1.5 relative z-10">
                        <div
                          className={`w-7 h-7 rounded-full flex items-center justify-center transition-colors ${
                            claim.status === 'PICKED_UP'
                              ? 'bg-[var(--primary)] text-white'
                              : 'bg-[var(--surface)] border border-[var(--border)] text-[var(--muted)]'
                          }`}
                        >
                          <Truck className="w-3.5 h-3.5" />
                        </div>
                        <span
                          className={`text-xs font-semibold ${
                            claim.status === 'PICKED_UP' ? 'text-[var(--text)]' : 'text-[var(--muted)]'
                          }`}
                        >
                          3. Rescued
                        </span>
                        <span className="text-[10px] text-[var(--muted)]">Handover complete</span>
                      </div>
                    </div>
                  </div>

                  {/* Notes & Address Footer */}
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 text-xs text-[var(--muted)] pt-1">
                    {claim.listing && (
                      <span className="flex items-center gap-1.5">
                        <MapPin className="w-3.5 h-3.5 text-[var(--primary)] shrink-0" />
                        <span>Pickup Location: <strong>{claim.listing.address}</strong></span>
                      </span>
                    )}
                    {claim.notes && (
                      <span className="italic truncate max-w-md">
                        &quot;{claim.notes}&quot;
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Rate this Donor Modal */}
        {ratingModalClaim && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-0 sm:p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
            <div className="w-full h-full sm:h-auto sm:max-w-md rounded-none sm:rounded-[12px] border-0 sm:border border-[var(--border)] bg-[var(--surface)] p-6 shadow-xl space-y-4 overflow-y-auto flex flex-col justify-between sm:justify-start">
              <div>
                <div className="space-y-1 mb-4">
                  <h3 className="text-base font-bold text-[var(--text)]">
                    Rate Donor Partner
                  </h3>
                  <p className="text-xs text-[var(--muted)]">
                    How was the food handover experience with{' '}
                    <strong className="text-[var(--text)]">
                      {ratingModalClaim.listing?.business_name || 'the donor'}
                    </strong>
                    ?
                  </p>
                </div>

                <form id="claim-rate-form" onSubmit={handleSubmitRating} className="space-y-4">
                  {/* Interactive Star Picker */}
                  <div className="py-2 text-center space-y-2">
                    <div className="flex justify-center">
                      <RatingStars
                        value={starRating}
                        onChange={(r) => setStarRating(r)}
                        size="lg"
                      />
                    </div>
                    <p className="text-xs font-semibold text-[var(--primary)] tabular-nums">
                      {starRating} out of 5 Stars
                    </p>
                  </div>

                  {/* Feedback Input */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="block text-xs font-semibold text-[var(--text)]">
                        Feedback &amp; Packaging Notes
                      </label>
                      <span className="text-[11px] text-[var(--muted)] tabular-nums">
                        {feedbackText.length}/500
                      </span>
                    </div>
                    <textarea
                      rows={3}
                      maxLength={500}
                      value={feedbackText}
                      onChange={(e) => setFeedbackText(e.target.value)}
                      placeholder="Describe condition of food, cold storage hygiene, punctuality..."
                      className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-xs text-[var(--text)] outline-none focus:ring-1 focus:ring-[var(--primary)]"
                    />
                  </div>

                  {/* Modal Buttons */}
                  <div className="flex items-center justify-end gap-2 pt-2 border-t border-[var(--border)]">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setRatingModalClaim(null)}
                      className="text-xs"
                    >
                      Cancel
                    </Button>
                    <Button
                      type="submit"
                      variant="primary"
                      size="sm"
                      disabled={rateClaimMutation.isPending || starRating < 1 || starRating > 5}
                      className="text-xs font-semibold gap-1.5"
                    >
                      <CheckCircle2 className="w-4 h-4" />
                      <span>{rateClaimMutation.isPending ? 'Submitting...' : 'Submit Rating'}</span>
                    </Button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        )}
      </div>
    </FeatureGuard>
  );
};

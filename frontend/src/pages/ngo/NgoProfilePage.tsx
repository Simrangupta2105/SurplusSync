import React, { useState } from 'react';
import {
  Star,
  Lock,
  Edit3,
  Clock,
  Building2,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Calendar,
  PackageCheck,
  ShieldCheck,
  X,
  MapPin,
  Truck,
  MessageSquare,
  ShieldAlert,
} from 'lucide-react';
import { Button } from '../../components/ui/Button';
import { PageHeader } from '../../components/ui/PageHeader';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { RatingStars } from '../../components/ui/RatingStars';
import { EmptyState } from '../../components/ui/EmptyState';
import {
  useCurrentUser,
  usePendingRatings,
  useMyRatings,
  useRateClaim,
  useUpdateRating,
} from '../../hooks/useData';
import type { PendingRating, Rating } from '../../types';

interface NgoProfilePageProps {
  onTriggerToast: (msg: string) => void;
  onNavigate?: (path: string) => void;
}

export const NgoProfilePage: React.FC<NgoProfilePageProps> = ({
  onTriggerToast,
  onNavigate,
}) => {
  const { data: user } = useCurrentUser();
  const isVerified = user?.organization?.is_verified ?? false;
  const orgName = user?.organization?.name || 'Relief Foundation';

  // Active Tab: 'pending' | 'reviews' | 'profile'
  const [activeTab, setActiveTab] = useState<'pending' | 'reviews' | 'profile'>('pending');
  const [reviewsPage, setReviewsPage] = useState<number>(1);

  // Queries
  const {
    data: pendingRatings = [],
    isLoading: isPendingLoading,
    isError: isPendingError,
    refetch: refetchPending,
  } = usePendingRatings();

  const {
    data: myRatingsData,
    isLoading: isReviewsLoading,
    isError: isReviewsError,
    refetch: refetchReviews,
  } = useMyRatings(reviewsPage);

  const myReviews: Rating[] = myRatingsData?.results || [];

  // Mutations
  const rateClaimMutation = useRateClaim();
  const updateRatingMutation = useUpdateRating();

  // Modal State: Rate a Pending Claim
  const [ratingTarget, setRatingTarget] = useState<PendingRating | null>(null);
  const [newStars, setNewStars] = useState<number>(5);
  const [newComment, setNewComment] = useState<string>('');
  const [rateError, setRateError] = useState<string | null>(null);

  // Modal State: Edit an Existing Rating
  const [editingRating, setEditingRating] = useState<Rating | null>(null);
  const [editStars, setEditStars] = useState<number>(5);
  const [editComment, setEditComment] = useState<string>('');
  const [editError, setEditError] = useState<string | null>(null);

  // Open "Rate Donor" modal
  const handleOpenRateModal = (pending: PendingRating) => {
    setRatingTarget(pending);
    setNewStars(5);
    setNewComment('');
    setRateError(null);
  };

  // Submit new rating
  const handleSubmitRating = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ratingTarget) return;

    if (newStars < 1 || newStars > 5) {
      setRateError('Please select a star rating between 1 and 5.');
      return;
    }

    setRateError(null);
    const claimId = ratingTarget.claim_id ?? ratingTarget.id;

    rateClaimMutation.mutate(
      {
        claimId,
        payload: {
          stars: newStars,
          comment: newComment.trim(),
        },
      },
      {
        onSuccess: () => {
          onTriggerToast(`Rating submitted successfully for ${ratingTarget.donor_name}!`);
          setRatingTarget(null);
          // Switch to reviews tab to view newly added review
          setActiveTab('reviews');
        },
        onError: (err: unknown) => {
          const message =
            (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            (err as Error)?.message ||
            'Failed to submit rating. Please try again.';
          setRateError(message);
        },
      }
    );
  };

  // Open "Edit Rating" modal
  const handleOpenEditModal = (rating: Rating) => {
    setEditingRating(rating);
    setEditStars(rating.stars);
    setEditComment(rating.comment || '');
    setEditError(null);
  };

  // Submit edited rating
  const handleSubmitEdit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingRating) return;

    if (editStars < 1 || editStars > 5) {
      setEditError('Please select a star rating between 1 and 5.');
      return;
    }

    setEditError(null);

    updateRatingMutation.mutate(
      {
        ratingId: editingRating.id,
        payload: {
          stars: editStars,
          comment: editComment.trim(),
        },
      },
      {
        onSuccess: () => {
          onTriggerToast('Review updated successfully.');
          setEditingRating(null);
        },
        onError: (err: unknown) => {
          const message =
            (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            (err as Error)?.message ||
            'Failed to update review. Edit window may have expired.';
          setEditError(message);
        },
      }
    );
  };

  const formatDate = (isoString?: string | null) => {
    if (!isoString) return 'Recent';
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    } catch {
      return isoString;
    }
  };

  // Guard against business users accessing NGO profile
  if (user && user.organization && user.organization.type !== 'NGO') {
    return (
      <div
        id="ngo-profile-access-restricted"
        className="rounded-[12px] border border-[var(--color-danger-border)] bg-[var(--color-danger-subtle)] p-8 text-center space-y-4 max-w-lg mx-auto my-12"
      >
        <div className="w-12 h-12 rounded-full bg-[var(--color-danger)]/15 text-[var(--color-danger)] flex items-center justify-center mx-auto">
          <ShieldAlert className="w-6 h-6" />
        </div>
        <div className="space-y-1.5">
          <h2 className="text-lg font-bold text-[var(--text)]">Access Restricted</h2>
          <p className="text-xs text-[var(--muted)] leading-relaxed">
            The NGO Profile and Rating Management portal is exclusively reserved for registered NGO relief partners. Business accounts cannot access this page.
          </p>
        </div>
        {onNavigate && (
          <Button
            variant="primary"
            size="sm"
            onClick={() => onNavigate('dashboard')}
            className="text-xs mt-2"
          >
            Return to Dashboard
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Page Header */}
      <PageHeader
        title="NGO Profile &amp; Donor Ratings"
        description="Manage your relief operations profile, review donor handover experiences, and rate business partners for completed pickups."
      />

      {/* Unverified Warning Banner */}
      {!isVerified && (
        <div
          id="unverified-ngo-banner"
          className="rounded-[12px] border border-[var(--color-warning-border)] bg-[var(--color-warning-subtle)] p-4 sm:p-5 text-[var(--color-warning)] shadow-xs flex items-start gap-3.5"
        >
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h4 className="text-sm font-bold text-[var(--text)]">
              Verification Required to Rate Donors
            </h4>
            <p className="text-xs text-[var(--text)]/80 leading-relaxed">
              Complete verification to rate donor businesses. Your relief entity documentation is
              currently undergoing administrative audit. Verified NGOs can rate food handover
              condition, cold-chain integrity, and donor responsiveness.
            </p>
          </div>
        </div>
      )}

      {/* Organization Snapshot Summary Card */}
      <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 shadow-xs">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-[10px] bg-[var(--primary)]/10 text-[var(--primary)] flex items-center justify-center shrink-0 border border-[var(--primary)]/20">
              <Building2 className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-[var(--text)]">{orgName}</h3>
                <StatusBadge variant={isVerified ? 'success' : 'warning'} size="sm" dot>
                  {isVerified ? 'Verified NGO' : 'Pending Verification'}
                </StatusBadge>
              </div>
              <p className="text-xs text-[var(--muted)] flex items-center gap-2 mt-0.5">
                <span>Account: {user?.email || 'ngo@surplussync.com'}</span>
                <span>•</span>
                <span>Role: {user?.role || 'ORGANIZATION_LEAD'}</span>
              </p>
            </div>
          </div>

          {/* Quick Metrics */}
          <div className="flex items-center gap-3 w-full sm:w-auto pt-2 sm:pt-0 border-t sm:border-t-0 border-[var(--border)]">
            <div className="p-2.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] text-center min-w-[90px]">
              <span className="block text-xs text-[var(--muted)] font-medium">Pending</span>
              <span className="text-base font-bold tabular-nums text-[var(--primary)]">
                {isVerified ? pendingRatings.length : '—'}
              </span>
            </div>
            <div className="p-2.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] text-center min-w-[90px]">
              <span className="block text-xs text-[var(--muted)] font-medium">Reviews Given</span>
              <span className="text-base font-bold tabular-nums text-[var(--text)]">
                {isVerified ? (myRatingsData?.count ?? myReviews.length) : '—'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-[var(--border)] pb-2 overflow-x-auto">
        <button
          type="button"
          onClick={() => setActiveTab('pending')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-[8px] text-xs font-semibold transition-all cursor-pointer ${
            activeTab === 'pending'
              ? 'bg-[var(--primary)] text-white shadow-xs'
              : 'text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)]'
          }`}
        >
          <Clock className="w-3.5 h-3.5" />
          <span>Pending Ratings</span>
          {isVerified && pendingRatings.length > 0 && (
            <span
              className={`px-1.5 py-0.2 rounded-full text-[10px] font-bold ${
                activeTab === 'pending'
                  ? 'bg-white/20 text-white'
                  : 'bg-[var(--primary)]/15 text-[var(--primary)]'
              }`}
            >
              {pendingRatings.length}
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('reviews')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-[8px] text-xs font-semibold transition-all cursor-pointer ${
            activeTab === 'reviews'
              ? 'bg-[var(--primary)] text-white shadow-xs'
              : 'text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)]'
          }`}
        >
          <Star className="w-3.5 h-3.5" />
          <span>My Reviews</span>
          {isVerified && (myRatingsData?.count ?? myReviews.length) > 0 && (
            <span
              className={`px-1.5 py-0.2 rounded-full text-[10px] font-bold ${
                activeTab === 'reviews'
                  ? 'bg-white/20 text-white'
                  : 'bg-[var(--surface-2)] text-[var(--muted)]'
              }`}
            >
              {myRatingsData?.count ?? myReviews.length}
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('profile')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-[8px] text-xs font-semibold transition-all cursor-pointer ${
            activeTab === 'profile'
              ? 'bg-[var(--primary)] text-white shadow-xs'
              : 'text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)]'
          }`}
        >
          <Building2 className="w-3.5 h-3.5" />
          <span>Hub & Fleet Profile</span>
        </button>
      </div>

      {/* Tab 1: Pending Ratings */}
      {activeTab === 'pending' && (
        <div className="space-y-4">
          {!isVerified ? (
            <div className="p-8 text-center rounded-[12px] border border-dashed border-[var(--border)] bg-[var(--surface)] space-y-3">
              <ShieldCheck className="w-10 h-10 text-[var(--color-warning)] mx-auto opacity-70" />
              <div className="space-y-1">
                <h4 className="text-sm font-semibold text-[var(--text)]">
                  Verification Pending
                </h4>
                <p className="text-xs text-[var(--muted)] max-w-md mx-auto">
                  Complete verification to rate donor businesses. Once approved, all completed
                  rescue dispatches will appear here ready for feedback.
                </p>
              </div>
            </div>
          ) : isPendingLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((n) => (
                <div
                  key={n}
                  className="h-28 rounded-[12px] bg-[var(--surface-2)] border border-[var(--border)] animate-pulse"
                />
              ))}
            </div>
          ) : isPendingError ? (
            <div className="p-6 rounded-[12px] border border-[var(--color-danger-border)] bg-[var(--color-danger-subtle)] text-center space-y-3">
              <AlertTriangle className="w-6 h-6 text-[var(--color-danger)] mx-auto" />
              <p className="text-xs text-[var(--color-danger)]">
                Unable to load pending ratings from the server.
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => refetchPending()}
                className="text-xs gap-1.5"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Retry</span>
              </Button>
            </div>
          ) : pendingRatings.length === 0 ? (
            <EmptyState
              icon={PackageCheck}
              title="All Caught Up!"
              description="No pending ratings - all picked-up donations have been reviewed"
              action={
                onNavigate ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onNavigate('feed')}
                    className="text-xs"
                  >
                    Browse Live Food Feed
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <div className="grid grid-cols-1 gap-3.5">
              {pendingRatings.map((item) => (
                <div
                  key={item.id}
                  id={`pending-rating-${item.id}`}
                  className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:border-[var(--primary)]/40 transition-colors"
                >
                  <div className="space-y-1.5 min-w-0">
                    <div className="flex items-center gap-2">
                      <h4 className="text-sm font-bold text-[var(--text)] truncate">
                        {item.donor_name}
                      </h4>
                      {item.donor_rating_avg !== null && item.donor_rating_avg !== undefined && (
                        <div className="flex items-center gap-1 text-[11px] font-semibold text-[var(--color-warning)]">
                          <Star className="w-3 h-3 fill-[var(--color-warning)]" />
                          <span>{item.donor_rating_avg.toFixed(1)}</span>
                          <span className="text-[var(--muted)]">({item.donor_rating_count})</span>
                        </div>
                      )}
                    </div>
                    <p className="text-xs text-[var(--text)] font-medium">
                      Item: <span className="font-semibold">{item.item || item.listing_title}</span>
                      {item.quantity ? ` • Quantity: ${item.quantity}` : ''}
                    </p>
                    <div className="flex items-center gap-3 text-[11px] text-[var(--muted)]">
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        <span>Picked Up: {formatDate(item.pickup_date || item.pickup_eta)}</span>
                      </span>
                    </div>
                  </div>

                  <div className="shrink-0 flex items-center gap-2">
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => handleOpenRateModal(item)}
                      className="text-xs font-semibold gap-1.5 shadow-xs"
                    >
                      <Star className="w-3.5 h-3.5 fill-current" />
                      <span>Rate Donor</span>
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 2: My Reviews */}
      {activeTab === 'reviews' && (
        <div className="space-y-4">
          {!isVerified ? (
            <div className="p-8 text-center rounded-[12px] border border-dashed border-[var(--border)] bg-[var(--surface)] space-y-3">
              <ShieldCheck className="w-10 h-10 text-[var(--color-warning)] mx-auto opacity-70" />
              <div className="space-y-1">
                <h4 className="text-sm font-semibold text-[var(--text)]">
                  Verification Required
                </h4>
                <p className="text-xs text-[var(--muted)] max-w-md mx-auto">
                  Complete verification to rate donor businesses and inspect historical review logs.
                </p>
              </div>
            </div>
          ) : isReviewsLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((n) => (
                <div
                  key={n}
                  className="h-28 rounded-[12px] bg-[var(--surface-2)] border border-[var(--border)] animate-pulse"
                />
              ))}
            </div>
          ) : isReviewsError ? (
            <div className="p-6 rounded-[12px] border border-[var(--color-danger-border)] bg-[var(--color-danger-subtle)] text-center space-y-3">
              <AlertTriangle className="w-6 h-6 text-[var(--color-danger)] mx-auto" />
              <p className="text-xs text-[var(--color-danger)]">
                Unable to load your past reviews from the server.
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => refetchReviews()}
                className="text-xs gap-1.5"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Retry</span>
              </Button>
            </div>
          ) : myReviews.length === 0 ? (
            <EmptyState
              icon={Star}
              title="No Reviews Submitted Yet"
              description="No reviews submitted yet"
              action={
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setActiveTab('pending')}
                  className="text-xs"
                >
                  View Pending Ratings
                </Button>
              }
            />
          ) : (
            <div className="space-y-3.5">
              <div className="grid grid-cols-1 gap-3.5">
                {myReviews.map((review) => {
                  const isWithinWindow = Boolean(review.is_editable);

                  return (
                    <div
                      key={review.id}
                      id={`my-rating-${review.id}`}
                      className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5 shadow-xs space-y-3"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[var(--border)]/60 pb-3">
                        <div>
                          <h4 className="text-sm font-bold text-[var(--text)]">
                            {review.business_name || 'Donor Partner'}
                          </h4>
                          <span className="text-[11px] text-[var(--muted)]">
                            Submitted on {formatDate(review.created_at)}
                          </span>
                        </div>

                        <div className="flex items-center gap-3">
                          <RatingStars value={review.stars} readOnly size="sm" showNumber />

                          {isWithinWindow ? (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleOpenEditModal(review)}
                              className="text-xs gap-1 py-1 h-7 text-[var(--primary)] border-[var(--primary)]/30 hover:bg-[var(--primary)]/10"
                            >
                              <Edit3 className="w-3 h-3" />
                              <span>Edit</span>
                            </Button>
                          ) : (
                            <span
                              title="The 7-day edit window for this rating has expired"
                              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[6px] text-[10px] font-semibold bg-[var(--surface-2)] text-[var(--muted)] border border-[var(--border)]"
                            >
                              <Lock className="w-3 h-3 text-[var(--muted)]" />
                              <span>Locked (7-day edit window passed)</span>
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Comment */}
                      <div className="text-xs text-[var(--text)] leading-relaxed bg-[var(--surface-2)]/50 p-3 rounded-[8px] border border-[var(--border)]/50">
                        {review.comment ? (
                          <p>{review.comment}</p>
                        ) : (
                          <p className="italic text-[var(--muted)]">No written feedback provided.</p>
                        )}
                      </div>

                      {isWithinWindow && (
                        <div className="text-[10px] text-[var(--muted)] flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          <span>
                            Editable until {formatDate(review.edit_deadline)} (7-day window)
                          </span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Pagination if multiple pages */}
              {myRatingsData && myRatingsData.count > 10 && (
                <div className="flex items-center justify-between pt-2">
                  <span className="text-xs text-[var(--muted)]">
                    Showing {myReviews.length} of {myRatingsData.count} reviews
                  </span>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!myRatingsData.previous}
                      onClick={() => setReviewsPage((p) => Math.max(1, p - 1))}
                      className="text-xs"
                    >
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!myRatingsData.next}
                      onClick={() => setReviewsPage((p) => p + 1)}
                      className="text-xs"
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Hub & Fleet Profile */}
      {activeTab === 'profile' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4">
            <h4 className="text-sm font-bold text-[var(--text)] flex items-center gap-2">
              <MapPin className="w-4 h-4 text-[var(--primary)]" />
              <span>Distribution Hub & Coverage</span>
            </h4>
            <div className="space-y-2 text-xs">
              <div className="p-2.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)]">
                <span className="text-[10px] font-semibold uppercase text-[var(--muted)] block">
                  Registered Hub Address
                </span>
                <span className="font-medium text-[var(--text)]">
                  HK Hill, West of Chord Road, Bengaluru 560010
                </span>
              </div>
              <div className="p-2.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)]">
                <span className="text-[10px] font-semibold uppercase text-[var(--muted)] block">
                  Operations Dispatch Radius
                </span>
                <span className="font-medium text-[var(--primary)]">15 km Radius Horizon</span>
              </div>
            </div>
          </div>

          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4">
            <h4 className="text-sm font-bold text-[var(--text)] flex items-center gap-2">
              <Truck className="w-4 h-4 text-[var(--primary)]" />
              <span>Rescue Transport Capacities</span>
            </h4>
            <div className="space-y-2 text-xs">
              <div className="p-2.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-[var(--color-success)] shrink-0" />
                <span className="font-medium">1x Insulated Refrigerated Transit Van (1.5 Ton)</span>
              </div>
              <div className="p-2.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-[var(--color-success)] shrink-0" />
                <span className="font-medium">2x Electric Three-Wheeler Cargo Units</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Rate Donor Partner */}
      {ratingTarget && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="rate-donor-modal-title"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150"
        >
          <div className="w-full max-w-md rounded-[14px] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl space-y-4 animate-in zoom-in-95 duration-150">
            <div className="flex items-start justify-between">
              <div>
                <h3 id="rate-donor-modal-title" className="text-base font-bold text-[var(--text)]">
                  Rate Donor Partner
                </h3>
                <p className="text-xs text-[var(--muted)] mt-0.5">
                  How was your food rescue handover experience with{' '}
                  <strong className="text-[var(--text)]">{ratingTarget.donor_name}</strong>?
                </p>
              </div>
              <button
                type="button"
                onClick={() => setRatingTarget(null)}
                className="p-1 rounded-[6px] text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)] cursor-pointer"
                aria-label="Close dialog"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {rateError && (
              <div className="p-3 rounded-[8px] bg-[var(--color-danger-subtle)] border border-[var(--color-danger-border)] text-[var(--color-danger)] text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{rateError}</span>
              </div>
            )}

            <form onSubmit={handleSubmitRating} className="space-y-4">
              {/* Star Rating Picker */}
              <div className="py-2 text-center space-y-2 bg-[var(--surface-2)]/60 rounded-[10px] p-4 border border-[var(--border)]">
                <span className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wider block">
                  Select Rating
                </span>
                <div className="flex justify-center">
                  <RatingStars
                    value={newStars}
                    onChange={(stars) => setNewStars(stars)}
                    size="lg"
                  />
                </div>
                <p className="text-xs font-bold text-[var(--primary)] tabular-nums">
                  {newStars} of 5 Stars
                </p>
              </div>

              {/* Comment Input */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <label htmlFor="rate-comment-input" className="font-semibold text-[var(--text)] flex items-center gap-1">
                    <MessageSquare className="w-3.5 h-3.5 text-[var(--primary)]" />
                    <span>Review &amp; Handover Feedback (Optional)</span>
                  </label>
                  <span
                    className={`tabular-nums text-[10px] ${
                      newComment.length > 450 ? 'text-[var(--color-warning)] font-bold' : 'text-[var(--muted)]'
                    }`}
                  >
                    {newComment.length} / 500
                  </span>
                </div>
                <textarea
                  id="rate-comment-input"
                  rows={3}
                  maxLength={500}
                  value={newComment}
                  onChange={(e) => setNewComment(e.target.value)}
                  placeholder="Note packaging quality, temperature retention, punctuality, and staff courtesy..."
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-xs text-[var(--text)] outline-none focus:ring-1 focus:ring-[var(--primary)] placeholder:text-[var(--muted)]"
                />
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-2 pt-2 border-t border-[var(--border)]">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setRatingTarget(null)}
                  className="text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  disabled={rateClaimMutation.isPending}
                  className="text-xs font-semibold gap-1.5"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  <span>{rateClaimMutation.isPending ? 'Submitting...' : 'Submit Rating'}</span>
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Edit Existing Rating */}
      {editingRating && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="edit-review-modal-title"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150"
        >
          <div className="w-full max-w-md rounded-[14px] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl space-y-4 animate-in zoom-in-95 duration-150">
            <div className="flex items-start justify-between">
              <div>
                <h3 id="edit-review-modal-title" className="text-base font-bold text-[var(--text)]">
                  Edit Review
                </h3>
                <p className="text-xs text-[var(--muted)] mt-0.5">
                  Update rating and notes for{' '}
                  <strong className="text-[var(--text)]">
                    {editingRating.business_name || 'Donor Partner'}
                  </strong>
                  .
                </p>
              </div>
              <button
                type="button"
                onClick={() => setEditingRating(null)}
                className="p-1 rounded-[6px] text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)] cursor-pointer"
                aria-label="Close dialog"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {editError && (
              <div className="p-3 rounded-[8px] bg-[var(--color-danger-subtle)] border border-[var(--color-danger-border)] text-[var(--color-danger)] text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{editError}</span>
              </div>
            )}

            <form onSubmit={handleSubmitEdit} className="space-y-4">
              {/* Star Rating Picker */}
              <div className="py-2 text-center space-y-2 bg-[var(--surface-2)]/60 rounded-[10px] p-4 border border-[var(--border)]">
                <span className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wider block">
                  Updated Rating
                </span>
                <div className="flex justify-center">
                  <RatingStars
                    value={editStars}
                    onChange={(stars) => setEditStars(stars)}
                    size="lg"
                  />
                </div>
                <p className="text-xs font-bold text-[var(--primary)] tabular-nums">
                  {editStars} of 5 Stars
                </p>
              </div>

              {/* Comment Input */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <label htmlFor="edit-comment-input" className="font-semibold text-[var(--text)] flex items-center gap-1">
                    <MessageSquare className="w-3.5 h-3.5 text-[var(--primary)]" />
                    <span>Review Feedback</span>
                  </label>
                  <span
                    className={`tabular-nums text-[10px] ${
                      editComment.length > 450 ? 'text-[var(--color-warning)] font-bold' : 'text-[var(--muted)]'
                    }`}
                  >
                    {editComment.length} / 500
                  </span>
                </div>
                <textarea
                  id="edit-comment-input"
                  rows={3}
                  maxLength={500}
                  value={editComment}
                  onChange={(e) => setEditComment(e.target.value)}
                  placeholder="Update your review notes..."
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-xs text-[var(--text)] outline-none focus:ring-1 focus:ring-[var(--primary)]"
                />
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-2 pt-2 border-t border-[var(--border)]">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setEditingRating(null)}
                  className="text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  disabled={updateRatingMutation.isPending}
                  className="text-xs font-semibold gap-1.5"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  <span>{updateRatingMutation.isPending ? 'Saving...' : 'Save Changes'}</span>
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

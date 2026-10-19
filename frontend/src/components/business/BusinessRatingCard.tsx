import React from 'react';
import { Star, ShieldCheck, MessageSquare, Info } from 'lucide-react';
import { RatingStars } from '../ui/RatingStars';
import { useBusinessRatings } from '../../hooks/useData';
import { Skeleton } from '../ui/Skeleton';
import { cn } from '../../lib/utils';

interface BusinessRatingCardProps {
  businessId: number;
  className?: string;
}

export const BusinessRatingCard: React.FC<BusinessRatingCardProps> = ({
  businessId,
  className,
}) => {
  const { data, isLoading, isError } = useBusinessRatings(businessId);

  const ratingAvg = data?.rating_avg;
  const ratingCount = data?.rating_count ?? 0;
  const breakdown = data?.breakdown || { '1': 0, '2': 0, '3': 0, '4': 0, '5': 0 };
  const recentReviews = data?.recent_reviews || [];

  const formatDate = (isoString?: string) => {
    if (!isoString) return '';
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

  if (isLoading) {
    return (
      <div
        id="business-rating-card-loading"
        className={cn(
          'rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 shadow-xs space-y-5',
          className
        )}
      >
        <div className="flex items-center justify-between">
          <div className="space-y-1.5">
            <Skeleton className="h-5 w-32" />
            <Skeleton className="h-3 w-56" />
          </div>
          <Skeleton className="h-6 w-20 rounded-full" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="space-y-2">
            <Skeleton className="h-10 w-20" />
            <Skeleton className="h-4 w-32" />
          </div>
          <div className="md:col-span-2 space-y-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-3 w-full" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div
        id="business-rating-card-error"
        className={cn(
          'rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 text-center text-xs text-[var(--muted)]',
          className
        )}
      >
        <span>Community ratings are temporarily unavailable.</span>
      </div>
    );
  }

  return (
    <div
      id="business-rating-card"
      className={cn(
        'rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 shadow-xs space-y-6',
        className
      )}
      aria-label="Your rating and NGO reviews"
    >
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[var(--border)] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-bold text-[var(--text)]">Your Rating</h2>
            <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20">
              <ShieldCheck className="w-3 h-3" />
              <span>Verified NGO Reviews</span>
            </span>
          </div>
          <p className="text-xs text-[var(--muted)] mt-0.5">
            Community ratings and food handover feedback submitted by verified NGO relief partners.
          </p>
        </div>

        {/* Read-Only Notice Badge */}
        <div className="flex items-center gap-1.5 text-[11px] text-[var(--muted)] bg-[var(--surface-2)] px-2.5 py-1 rounded-[6px] border border-[var(--border)] self-start sm:self-auto shrink-0">
          <Info className="w-3.5 h-3.5 text-[var(--primary)]" />
          <span>Read-only • Replies disabled</span>
        </div>
      </div>

      {/* Main Stats & Breakdown Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-center">
        {/* Left: Overall Rating Average */}
        <div className="flex flex-col items-center sm:items-start text-center sm:text-left space-y-2 p-4 rounded-[10px] bg-[var(--surface-2)] border border-[var(--border)]">
          <span className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">
            Overall Score
          </span>
          <div className="flex items-baseline gap-2">
            <span
              id="business-rating-average"
              className="text-4xl font-extrabold tabular-nums text-[var(--text)] tracking-tight"
            >
              {ratingAvg !== null && ratingAvg !== undefined ? ratingAvg.toFixed(1) : '—'}
            </span>
            <span className="text-xs font-medium text-[var(--muted)]">/ 5.0</span>
          </div>
          <div className="flex items-center gap-1.5">
            <RatingStars
              value={ratingAvg || 0}
              size="md"
              readOnly
              showNumber={false}
            />
          </div>
          <span
            id="business-rating-count"
            className="text-xs text-[var(--muted)] font-medium tabular-nums"
          >
            {ratingCount > 0
              ? `Based on ${ratingCount} verified review${ratingCount === 1 ? '' : 's'}`
              : 'No reviews submitted yet'}
          </span>
        </div>

        {/* Right: Star Breakdown Bars (5 to 1) */}
        <div className="md:col-span-2 space-y-2">
          <span className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wider block mb-1">
            Rating Distribution
          </span>
          {[5, 4, 3, 2, 1].map((star) => {
            const count = breakdown[String(star)] || 0;
            const percentage = ratingCount > 0 ? Math.round((count / ratingCount) * 100) : 0;

            return (
              <div
                key={star}
                className="flex items-center gap-3 text-xs"
                aria-label={`${star} stars: ${count} reviews (${percentage}%)`}
              >
                <span className="w-12 font-medium text-[var(--muted)] flex items-center gap-1 shrink-0">
                  <span>{star}</span>
                  <Star className="w-3 h-3 fill-[var(--color-warning)] text-[var(--color-warning)]" />
                </span>

                <div className="flex-1 h-2 rounded-full bg-[var(--surface-2)] overflow-hidden border border-[var(--border)]/60">
                  <div
                    className="h-full bg-[var(--color-warning)] rounded-full transition-all duration-300"
                    style={{ width: `${percentage}%` }}
                  />
                </div>

                <span className="w-16 text-right tabular-nums text-[var(--muted)] shrink-0 font-medium text-[11px]">
                  {count} <span className="opacity-70">({percentage}%)</span>
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Latest Reviews Section */}
      <div className="pt-4 border-t border-[var(--border)] space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text)] flex items-center gap-1.5">
            <MessageSquare className="w-3.5 h-3.5 text-[var(--primary)]" />
            <span>Latest NGO Reviews (Up to 5)</span>
          </h3>
          <span className="text-[11px] text-[var(--muted)]">
            Showing {recentReviews.length} of {ratingCount}
          </span>
        </div>

        {recentReviews.length === 0 ? (
          <div
            id="business-no-reviews"
            className="py-8 text-center text-xs text-[var(--muted)] rounded-[8px] border border-dashed border-[var(--border)] bg-[var(--surface-2)]/40 p-6 space-y-1.5"
          >
            <p className="font-semibold text-[var(--text)]">No Donor Ratings Received Yet</p>
            <p className="max-w-md mx-auto text-[11px]">
              Once verified NGOs complete a surplus food rescue and submit their handover evaluation,
              their ratings and comments will appear here.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-2.5" id="business-recent-reviews-list">
            {recentReviews.map((rev) => (
              <div
                key={rev.id}
                className="p-3.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] space-y-1.5"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-[var(--text)]">
                      {rev.ngo_name || 'Verified NGO Relief Partner'}
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--primary)]/10 text-[var(--primary)] font-medium border border-[var(--primary)]/20">
                      Verified NGO
                    </span>
                  </div>
                  <div className="flex items-center gap-2.5">
                    <RatingStars value={rev.stars} size="sm" readOnly showNumber />
                    <span className="text-[11px] text-[var(--muted)]">
                      {formatDate(rev.created_at)}
                    </span>
                  </div>
                </div>

                <p className="text-xs text-[var(--text)]/90 leading-relaxed italic">
                  {rev.comment ? `"${rev.comment}"` : <span className="text-[var(--muted)] not-italic">No written comment provided.</span>}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

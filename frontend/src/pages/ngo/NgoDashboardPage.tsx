import React from 'react';
import {
  HeartHandshake,
  MapPin,
  Clock,
  Sparkles,
  ArrowRight,
  TrendingUp,
  ShieldCheck,
  CheckCircle2,
  Package,
} from 'lucide-react';
import { Button } from '../../components/ui/Button';
import { PageHeader } from '../../components/ui/PageHeader';
import { StatCard } from '../../components/ui/StatCard';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { ExpiryPill } from '../../components/ui/ExpiryPill';
import { RatingStars } from '../../components/ui/RatingStars';
import { FeatureGuard } from '../../components/FeatureGuard';
import {
  useDonationListings,
  useDonationClaims,
  useImpactMetrics,
  useDonors,
} from '../../hooks/useData';
import type { DonationListing, DonationClaim } from '../../types';

interface NgoDashboardPageProps {
  onTriggerToast: (msg: string) => void;
  onNavigate: (path: string) => void;
  onSelectListingForClaim?: (listing: DonationListing) => void;
}

export const NgoDashboardPage: React.FC<NgoDashboardPageProps> = ({
  onTriggerToast: _onTriggerToast,
  onNavigate,
  onSelectListingForClaim,
}) => {
  const { data: listings, isLoading: isListingsLoading } = useDonationListings();
  const { data: claims, isLoading: isClaimsLoading } = useDonationClaims();
  const { data: impact } = useImpactMetrics();
  const { data: donors } = useDonors();

  const availableListings = (listings || []).filter((l) => l.status === 'AVAILABLE');
  const activeClaims = (claims || []).filter(
    (c) => c.status === 'PENDING' || c.status === 'CONFIRMED'
  );

  // Computations
  const totalMeals = Math.round((impact?.kg_diverted || 3240) / 0.42);
  const avgDonorRating = donors && donors.length > 0
    ? Number((donors.reduce((acc, d) => acc + d.rating, 0) / donors.length).toFixed(1))
    : 4.8;

  return (
    <FeatureGuard feature="marketplace_listings" featureName="NGO Rescue Operations">
      <div className="space-y-6 animate-in fade-in duration-200">
        {/* Header */}
        <PageHeader
          title="NGO Operations Hub"
          description="Real-time surplus food dispatch and rescue coordinate center for verified hunger-relief organizations."
          action={
            <Button
              variant="primary"
              size="sm"
              onClick={() => onNavigate('feed')}
              className="gap-1.5 shadow-xs text-xs font-semibold"
            >
              <HeartHandshake className="w-4 h-4" />
              <span>Browse Food Feed</span>
              <ArrowRight className="w-3.5 h-3.5 ml-0.5" />
            </Button>
          }
        />

        {/* Top Metric Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          <StatCard
            title="Available Nearby"
            value={isListingsLoading ? '...' : availableListings.length}
            subtitle="Ready for pickup today"
            icon={Package}
            trend={{ value: `${availableListings.length} active`, isPositive: true }}
          />
          <StatCard
            title="In-Progress Claims"
            value={isClaimsLoading ? '...' : activeClaims.length}
            subtitle="Dispatches in transit"
            icon={Clock}
          />
          <StatCard
            title="Meals Distributed"
            value={totalMeals.toLocaleString('en-IN')}
            subtitle="From diverted food mass"
            icon={TrendingUp}
            trend={{ value: '+14% this month', isPositive: true }}
          />
          <StatCard
            title="Partner Satisfaction"
            value={
              <div className="flex items-center gap-1.5">
                <span>{avgDonorRating}</span>
                <span className="text-xs text-[var(--muted)] font-normal">/ 5.0</span>
              </div>
            }
            subtitle="Across verified donors"
            icon={ShieldCheck}
          />
        </div>

        {/* Bento Grid: Urgent Listings + Claims In Transit */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Urgent Food Listings (2 columns) */}
          <div className="lg:col-span-2 rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-[var(--text)] flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-[var(--accent)]" />
                  <span>Immediate Rescues Nearby</span>
                </h3>
                <p className="text-xs text-[var(--muted)] mt-0.5">
                  Perishable items nearing expiration window. Sorted by urgency and proximity.
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onNavigate('feed')}
                className="text-xs text-[var(--primary)] hover:underline p-0 h-auto"
              >
                View Map ({availableListings.length}) →
              </Button>
            </div>

            {isListingsLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((n) => (
                  <div key={n} className="h-20 rounded-[8px] bg-[var(--surface-2)] animate-pulse" />
                ))}
              </div>
            ) : availableListings.length === 0 ? (
              <div className="py-12 text-center space-y-2">
                <CheckCircle2 className="w-8 h-8 text-[var(--color-success)] mx-auto opacity-70" />
                <p className="text-sm font-semibold text-[var(--text)]">All Clear</p>
                <p className="text-xs text-[var(--muted)] max-w-sm mx-auto">
                  No active perishable surplus in your radius right now. The simulation engine will broadcast new batches periodically.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {availableListings.slice(0, 4).map((listing: DonationListing) => (
                  <div
                    key={listing.id}
                    className="p-4 rounded-[10px] bg-[var(--surface-2)] border border-[var(--border)] flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:border-[var(--primary)]/40 transition-colors"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-sm text-[var(--text)]">
                          {listing.product_name}
                        </span>
                        <StatusBadge variant="neutral" size="sm">
                          {listing.quantity} {listing.unit}
                        </StatusBadge>
                        <ExpiryPill expiryDate={listing.expiry_date} />
                      </div>
                      <div className="flex items-center gap-3 text-xs text-[var(--muted)]">
                        <span className="font-medium text-[var(--text)]">
                          {listing.business_name}
                        </span>
                        <span>•</span>
                        <span className="flex items-center gap-1">
                          <MapPin className="w-3.5 h-3.5 text-[var(--primary)]" />
                          <span>{listing.distance_km || 3.2} km away</span>
                        </span>
                        <span>•</span>
                        <span>Window: {listing.pickup_window_start} - {listing.pickup_window_end}</span>
                      </div>
                    </div>

                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => {
                        if (onSelectListingForClaim) {
                          onSelectListingForClaim(listing);
                        } else {
                          onNavigate('feed');
                        }
                      }}
                      className="text-xs font-semibold gap-1.5 shrink-0 self-start sm:self-auto"
                    >
                      <span>Claim Food</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Active Claims & Dispatch Status (1 column) */}
          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 space-y-4 flex flex-col">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-[var(--text)]">My Dispatches</h3>
                <p className="text-xs text-[var(--muted)] mt-0.5">Active pickups & confirmations</p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onNavigate('claims')}
                className="text-xs text-[var(--primary)] hover:underline p-0 h-auto"
              >
                All Claims →
              </Button>
            </div>

            {isClaimsLoading ? (
              <div className="space-y-3">
                {[1, 2].map((n) => (
                  <div key={n} className="h-16 rounded-[8px] bg-[var(--surface-2)] animate-pulse" />
                ))}
              </div>
            ) : activeClaims.length === 0 ? (
              <div className="my-auto py-8 text-center space-y-2">
                <Clock className="w-8 h-8 text-[var(--muted)] mx-auto opacity-50" />
                <p className="text-xs font-semibold text-[var(--text)]">No Active Pickups</p>
                <p className="text-[11px] text-[var(--muted)] max-w-xs mx-auto">
                  Claim food surplus from the live feed to schedule volunteer pickups and coordinate arrival windows.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {activeClaims.slice(0, 3).map((c: DonationClaim) => (
                  <div
                    key={c.id}
                    onClick={() => onNavigate('claims')}
                    className="p-3.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] hover:border-[var(--primary)]/40 transition-colors cursor-pointer space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <StatusBadge
                        variant={c.status === 'CONFIRMED' ? 'success' : 'warning'}
                        size="sm"
                        dot
                      >
                        {c.status}
                      </StatusBadge>
                      <span className="text-[11px] text-[var(--muted)] tabular-nums">
                        ETA: {c.pickup_eta}
                      </span>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-[var(--text)]">
                        {c.listing?.product_name || `Listing #${c.listing_id}`}
                      </p>
                      <p className="text-[11px] text-[var(--muted)] truncate">
                        {c.listing?.business_name || 'Donor Partner Facility'}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Quick Partner Rating Insight */}
            <div className="mt-auto pt-4 border-t border-[var(--border)]">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[var(--muted)]">Average Donor Rating</span>
                <RatingStars value={avgDonorRating} size="sm" showNumber readOnly />
              </div>
            </div>
          </div>
        </div>
      </div>
    </FeatureGuard>
  );
};

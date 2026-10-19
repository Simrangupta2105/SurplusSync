import React, { useState, useMemo } from 'react';
import {
  List,
  Map as MapIcon,
  MapPin,
  Navigation,
  Clock,
  Sparkles,
  Search,
  Filter,
  CheckCircle2,
  Building2,
  ShieldCheck,
  Send,
} from 'lucide-react';
import { Button } from '../../components/ui/Button';
import { PageHeader } from '../../components/ui/PageHeader';
import { ExpiryPill } from '../../components/ui/ExpiryPill';
import { RatingStars } from '../../components/ui/RatingStars';
import { MapView, type MapMarker } from '../../components/ui/MapView';
import { Sheet } from '../../components/ui/Sheet';
import { FeatureGuard } from '../../components/FeatureGuard';
import { useDonationListings, useClaimListing } from '../../hooks/useData';
import type { DonationListing } from '../../types';

interface NgoFoodFeedPageProps {
  onTriggerToast: (msg: string) => void;
  onNavigate?: (path: string) => void;
  initialSelectedListing?: DonationListing | null;
}

export const NgoFoodFeedPage: React.FC<NgoFoodFeedPageProps> = ({
  onTriggerToast,
  onNavigate,
  initialSelectedListing = null,
}) => {
  const [viewMode, setViewMode] = useState<'list' | 'map'>('list');
  const [searchQuery, setSearchQuery] = useState('');
  const [radiusFilter, setRadiusFilter] = useState<number | null>(10); // km
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>({
    lat: 12.9716,
    lng: 77.5946,
  });
  const [selectedListing, setSelectedListing] = useState<DonationListing | null>(
    initialSelectedListing
  );

  // Claim Form State inside Sheet
  const [pickupEta, setPickupEta] = useState('Within 45 minutes');
  const [claimNotes, setClaimNotes] = useState('Volunteer dispatch van en-route with insulated cooler bins.');
  const [isClaimSubmitting, setIsClaimSubmitting] = useState(false);

  const { data: listings, isLoading } = useDonationListings();
  const claimMutation = useClaimListing();

  // Filter listings
  const filteredListings = useMemo(() => {
    return (listings || []).filter((l) => {
      if (l.status !== 'AVAILABLE') return false;
      if (radiusFilter !== null && (l.distance_km || 3.5) > radiusFilter) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        return (
          l.product_name.toLowerCase().includes(q) ||
          l.business_name.toLowerCase().includes(q) ||
          l.category.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [listings, radiusFilter, searchQuery]);

  // Handle Geolocation
  const handleUseLocation = () => {
    if (!navigator.geolocation) {
      onTriggerToast('Geolocation is not supported by your browser.');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setUserLocation({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
        });
        onTriggerToast('Updated your location coordinates for precision radius filtering.');
      },
      (err) => {
        const msg =
          err.code === 1
            ? 'Location permission was denied. Defaulting to Central Dispatch coordinates.'
            : 'Unable to fetch current GPS fix.';
        onTriggerToast(msg);
      }
    );
  };

  // Map Markers
  const mapMarkers: MapMarker[] = useMemo(() => {
    const markers: MapMarker[] = [];
    if (userLocation) {
      markers.push({
        id: 'user_location',
        latitude: userLocation.lat,
        longitude: userLocation.lng,
        title: 'Your Dispatch Hub',
        subtitle: 'Current Geolocation Center',
        isUserLocation: true,
      });
    }

    filteredListings.forEach((l) => {
      markers.push({
        id: l.id,
        latitude: l.latitude,
        longitude: l.longitude,
        title: `${l.product_name} (${l.quantity} ${l.unit})`,
        subtitle: `${l.business_name} • ${l.distance_km || 3.2} km away`,
        badge: `Pickup: ${l.pickup_window_start} - ${l.pickup_window_end}`,
        onClick: () => setSelectedListing(l),
      });
    });

    return markers;
  }, [filteredListings, userLocation]);

  // Submit Claim
  const handleConfirmClaim = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedListing) return;

    setIsClaimSubmitting(true);
    claimMutation.mutate(
      {
        listingId: selectedListing.id,
        eta: pickupEta,
        notes: claimNotes,
      },
      {
        onSuccess: () => {
          setIsClaimSubmitting(false);
          const listingName = selectedListing.product_name;
          setSelectedListing(null);
          onTriggerToast(`Claim confirmed for ${listingName}! Dispatch scheduled with donor.`);
          if (onNavigate) {
            onNavigate('claims');
          }
        },
        onError: (err: unknown) => {
          setIsClaimSubmitting(false);
          const msg = err instanceof Error ? err.message : 'Failed to register food rescue claim';
          onTriggerToast(msg);
        },
      }
    );
  };

  return (
    <FeatureGuard feature="marketplace_listings" featureName="Live Surplus Food Feed">
      <div className="space-y-6 animate-in fade-in duration-200">
        {/* Header with List/Map and Location Controls */}
        <PageHeader
          title="Food Surplus Feed"
          description="Live perishable food donations made available by local commercial kitchens and retailers for immediate distribution."
          action={
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleUseLocation}
                className="gap-1.5 text-xs text-[var(--muted)] hover:text-[var(--text)]"
              >
                <Navigation className="w-3.5 h-3.5 text-[var(--primary)]" />
                <span>Use My Location</span>
              </Button>
              <div className="flex rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-0.5">
                <button
                  type="button"
                  onClick={() => setViewMode('list')}
                  className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-[6px] transition-all ${
                    viewMode === 'list'
                      ? 'bg-[var(--primary)] text-white shadow-xs'
                      : 'text-[var(--muted)] hover:text-[var(--text)]'
                  }`}
                  aria-label="List view"
                >
                  <List className="w-3.5 h-3.5" />
                  <span>List</span>
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode('map')}
                  className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-[6px] transition-all ${
                    viewMode === 'map'
                      ? 'bg-[var(--primary)] text-white shadow-xs'
                      : 'text-[var(--muted)] hover:text-[var(--text)]'
                  }`}
                  aria-label="Map view"
                >
                  <MapIcon className="w-3.5 h-3.5" />
                  <span>Map</span>
                </button>
              </div>
            </div>
          }
        />

        {/* Filter Controls: Search and Radius Chips */}
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 p-3 rounded-[12px] bg-[var(--surface)] border border-[var(--border)]">
          {/* Search bar */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter by product name, category, or donor..."
              className="w-full pl-9 pr-3 py-1.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] text-xs text-[var(--text)] placeholder:text-[var(--muted)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
            />
          </div>

          {/* Radius Chips */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 md:pb-0">
            <span className="text-xs text-[var(--muted)] font-medium mr-1 flex items-center gap-1">
              <Filter className="w-3 h-3" />
              <span>Radius:</span>
            </span>
            {[
              { label: '2 km', value: 2 },
              { label: '5 km', value: 5 },
              { label: '10 km', value: 10 },
              { label: '25 km', value: 25 },
              { label: 'All', value: null },
            ].map((chip) => (
              <button
                key={chip.label}
                type="button"
                onClick={() => setRadiusFilter(chip.value)}
                className={`px-2.5 py-1 rounded-[6px] text-xs font-semibold border transition-all shrink-0 ${
                  radiusFilter === chip.value
                    ? 'bg-[var(--primary)] text-white border-[var(--primary)]'
                    : 'bg-[var(--surface-2)] text-[var(--muted)] border-[var(--border)] hover:text-[var(--text)]'
                }`}
              >
                {chip.label}
              </button>
            ))}
          </div>
        </div>

        {/* Main Content: Map or Grid */}
        {viewMode === 'map' ? (
          <div className="space-y-4">
            <div className="h-[460px] w-full rounded-[12px] border border-[var(--border)] overflow-hidden shadow-xs">
              <MapView
                markers={mapMarkers}
                center={userLocation ? [userLocation.lat, userLocation.lng] : [12.9716, 77.5946]}
                zoom={12}
                onMarkerSelect={(m) => {
                  const match = filteredListings.find((l) => l.id === m.id);
                  if (match) setSelectedListing(match);
                }}
              />
            </div>
            <p className="text-xs text-[var(--muted)] text-center">
              Click on any food marker to inspect donor verification, pickup windows, and initiate volunteer claim dispatch.
            </p>
          </div>
        ) : (
          <div>
            {isLoading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {[1, 2, 3, 4, 5, 6].map((n) => (
                  <div key={n} className="h-44 rounded-[12px] bg-[var(--surface-2)] animate-pulse" />
                ))}
              </div>
            ) : filteredListings.length === 0 ? (
              <div className="py-16 text-center rounded-[12px] border border-[var(--border)] bg-[var(--surface)] space-y-3">
                <CheckCircle2 className="w-10 h-10 text-[var(--color-success)] mx-auto opacity-70" />
                <div className="space-y-1">
                  <h4 className="text-sm font-semibold text-[var(--text)]">No Active Surplus in Range</h4>
                  <p className="text-xs text-[var(--muted)] max-w-sm mx-auto">
                    No donations currently meet your radius and keyword filters. Widen your radius or wait for real-time simulation engine alerts.
                  </p>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredListings.map((l: DonationListing) => (
                  <div
                    key={l.id}
                    className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xs flex flex-col justify-between space-y-3 hover:border-[var(--primary)]/50 transition-all group"
                  >
                    <div className="space-y-2">
                      {/* Top Bar: Category + Expiry Pill */}
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[11px] font-semibold text-[var(--primary)] tracking-wide uppercase">
                          {l.category}
                        </span>
                        <ExpiryPill expiryDate={l.expiry_date} />
                      </div>

                      {/* Product Name & Quantity */}
                      <div>
                        <h4 className="text-base font-bold text-[var(--text)] group-hover:text-[var(--primary)] transition-colors">
                          {l.product_name}
                        </h4>
                        <p className="text-xs font-semibold tabular-nums text-[var(--text)] mt-0.5">
                          {l.quantity} {l.unit} available
                        </p>
                      </div>

                      {/* Donor Info & Stars */}
                      <div className="pt-2 border-t border-[var(--border)] space-y-1.5">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-semibold text-[var(--text)] truncate">
                            {l.business_name}
                          </span>
                          <div className="flex items-center gap-1 shrink-0">
                            <RatingStars value={l.business_rating || 4.8} size="sm" showNumber readOnly />
                            {l.business_rating_count !== undefined && (
                              <span className="text-[10px] text-[var(--muted)] tabular-nums">
                                ({l.business_rating_count})
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-1.5 text-xs text-[var(--muted)]">
                          <MapPin className="w-3.5 h-3.5 text-[var(--primary)] shrink-0" />
                          <span className="truncate">{l.address}</span>
                          <span className="tabular-nums font-medium shrink-0">
                            • {l.distance_km || 3.2} km
                          </span>
                        </div>
                      </div>

                      {/* Pickup Window */}
                      <div className="flex items-center gap-1.5 text-[11px] text-[var(--muted)] bg-[var(--surface-2)] p-2 rounded-[6px]">
                        <Clock className="w-3.5 h-3.5 text-[var(--color-warning)] shrink-0" />
                        <span>Pickup: {l.pickup_window_start} - {l.pickup_window_end}</span>
                      </div>
                    </div>

                    {/* Claim Button */}
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => setSelectedListing(l)}
                      className="w-full gap-1.5 text-xs font-semibold mt-2"
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Inspect &amp; Claim Surplus</span>
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Listing Detail & Claim Sheet */}
        <Sheet
          isOpen={!!selectedListing}
          onClose={() => setSelectedListing(null)}
          title={selectedListing?.product_name || 'Listing Details'}
          description="Review perishable batch specifications and schedule an authorized volunteer dispatch."
        >
          {selectedListing && (
            <form onSubmit={handleConfirmClaim} className="space-y-5">
              {/* Product & Quantity Overview */}
              <div className="p-4 rounded-[10px] bg-[var(--surface-2)] border border-[var(--border)] space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-base font-bold text-[var(--text)]">
                      {selectedListing.product_name}
                    </h4>
                    <p className="text-xs text-[var(--muted)]">{selectedListing.category}</p>
                  </div>
                  <ExpiryPill expiryDate={selectedListing.expiry_date} />
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs pt-2 border-t border-[var(--border)]">
                  <div>
                    <span className="text-[var(--muted)]">Surplus Batch:</span>
                    <p className="font-semibold tabular-nums text-[var(--text)]">
                      {selectedListing.quantity} {selectedListing.unit}
                    </p>
                  </div>
                  <div>
                    <span className="text-[var(--muted)]">Distance:</span>
                    <p className="font-semibold text-[var(--text)]">
                      {selectedListing.distance_km || 3.2} km from hub
                    </p>
                  </div>
                </div>
              </div>

              {/* Donor Partner Details */}
              <div className="p-4 rounded-[10px] bg-[var(--surface-2)] border border-[var(--border)] space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 font-semibold text-xs text-[var(--text)]">
                    <Building2 className="w-4 h-4 text-[var(--primary)]" />
                    <span>{selectedListing.business_name}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <RatingStars
                      value={selectedListing.business_rating || 4.8}
                      size="sm"
                      showNumber
                      readOnly
                    />
                    {selectedListing.business_rating_count !== undefined && (
                      <span className="text-xs text-[var(--muted)] tabular-nums">
                        ({selectedListing.business_rating_count} reviews)
                      </span>
                    )}
                  </div>
                </div>
                <p className="text-xs text-[var(--muted)] flex items-start gap-1.5">
                  <MapPin className="w-3.5 h-3.5 text-[var(--primary)] shrink-0 mt-0.5" />
                  <span>{selectedListing.address}</span>
                </p>
                <div className="flex items-center gap-2 pt-2 border-t border-[var(--border)] text-[11px] text-[var(--muted)]">
                  <ShieldCheck className="w-3.5 h-3.5 text-[var(--color-success)]" />
                  <span>FSSAI Compliant Food Safety Packaging</span>
                </div>
              </div>

              {/* Pickup Window Specs */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-[var(--text)]">
                  Donor Pickup Schedule Window
                </label>
                <div className="p-3 rounded-[8px] bg-[var(--color-warning-subtle)] border border-[var(--color-warning-border)] text-xs text-[var(--color-warning)] flex items-center gap-2">
                  <Clock className="w-4 h-4 shrink-0" />
                  <span>
                    Must arrive between <strong>{selectedListing.pickup_window_start}</strong> and{' '}
                    <strong>{selectedListing.pickup_window_end}</strong>
                  </span>
                </div>
              </div>

              {/* Arrival ETA Selection */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-[var(--text)]">
                  Expected Arrival Time (ETA) *
                </label>
                <select
                  value={pickupEta}
                  onChange={(e) => setPickupEta(e.target.value)}
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2 text-xs text-[var(--text)] outline-none focus:ring-1 focus:ring-[var(--primary)]"
                >
                  <option value="Within 30 minutes">Within 30 minutes</option>
                  <option value="Within 45 minutes">Within 45 minutes</option>
                  <option value="Within 1 hour">Within 1 hour</option>
                  <option value="Within 2 hours">Within 2 hours</option>
                  <option value="Today before window close">Today before window close</option>
                </select>
              </div>

              {/* Volunteer Dispatch Notes */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-[var(--text)]">
                  Dispatch Notes &amp; Volunteer Vehicle Info
                </label>
                <textarea
                  rows={2}
                  value={claimNotes}
                  onChange={(e) => setClaimNotes(e.target.value)}
                  placeholder="e.g. Volunteer Driver Rajesh • Vehicle KA-01-AB-1234"
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2 text-xs text-[var(--text)] outline-none focus:ring-1 focus:ring-[var(--primary)]"
                />
              </div>

              {/* Submit CTA */}
              <div className="pt-2">
                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  disabled={isClaimSubmitting}
                  className="w-full gap-2 text-xs font-semibold"
                >
                  <Send className="w-4 h-4" />
                  <span>
                    {isClaimSubmitting ? 'Confirming Claim...' : 'Confirm Food Rescue Claim'}
                  </span>
                </Button>
              </div>
            </form>
          )}
        </Sheet>
      </div>
    </FeatureGuard>
  );
};

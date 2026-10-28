import React, { useState, useMemo } from 'react';
import {
  Store,
  Plus,
  Search,
  Flame,
  Snowflake,
  Sun,
  Thermometer,
  Clock,
  MapPin,
  Sparkles,
  LayoutGrid,
  List,
  Bell,
  ArrowRight,
  Package,
  X,
  Building2,
  Trash2,
} from 'lucide-react';
import { PageHeader } from '../components/ui/PageHeader';
import { Button } from '../components/ui/Button';
import { StatusBadge, type StatusVariant } from '../components/ui/StatusBadge';
import { RatingStars } from '../components/ui/RatingStars';
import { EmptyState } from '../components/ui/EmptyState';
import { Skeleton } from '../components/ui/Skeleton';
import {
  useSurplusListings,
  useCreateSurplusListing,
  useDeleteSurplusListing,
  useListingMatches,
  useNotifyListingMatches,
  useCreateDonationRequest,
  useCurrentUser,
  useBatches,
} from '../hooks/useData';
import type {
  SurplusListingItem,
  SurplusListingStatus,
  MatchingResultItem,
} from '../types';

interface SurplusMarketplacePageProps {
  onTriggerToast?: (msg: string) => void;
  onNavigate?: (path: string) => void;
}

const CATEGORIES = [
  'ALL',
  'PRODUCE',
  'DAIRY',
  'BAKERY',
  'MEAT',
  'PREPARED_MEALS',
  'PANTRY',
  'BEVERAGES',
  'OTHER',
];

export const SurplusMarketplacePage: React.FC<SurplusMarketplacePageProps> = ({
  onTriggerToast,
  onNavigate,
}) => {
  const { data: user } = useCurrentUser();
  const isBusiness = user?.organization?.type === 'BUSINESS';

  // Filters & View State
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState<'ALL' | SurplusListingStatus>('ALL');
  const [cookedOnly, setCookedOnly] = useState(false);
  const [temperatureFilter, setTemperatureFilter] = useState<'ALL' | 'AMBIENT' | 'CHILLED' | 'FROZEN'>('ALL');
  const [viewMode, setViewMode] = useState<'grid' | 'table'>('grid');

  // Modals state
  const [isBroadcastOpen, setIsBroadcastOpen] = useState(false);
  const [selectedListingForRequest, setSelectedListingForRequest] = useState<SurplusListingItem | null>(null);
  const [selectedListingForMatches, setSelectedListingForMatches] = useState<SurplusListingItem | null>(null);

  // Form state: Request Donation
  const [requestedQty, setRequestedQty] = useState('');
  const [requestedPickupTime, setRequestedPickupTime] = useState('');
  const [pickupNotes, setPickupNotes] = useState('');

  // Form state: Broadcast Surplus
  const [broadcastTitle, setBroadcastTitle] = useState('');
  const [broadcastDesc, setBroadcastDesc] = useState('');
  const [broadcastCategory, setBroadcastCategory] = useState('PRODUCE');
  const [broadcastQty, setBroadcastQty] = useState('');
  const [broadcastUnit, setBroadcastUnit] = useState('kg');
  const [broadcastTemp, setBroadcastTemp] = useState<'AMBIENT' | 'CHILLED' | 'FROZEN'>('AMBIENT');
  const [broadcastIsCooked, setBroadcastIsCooked] = useState(false);
  const [broadcastExpiry, setBroadcastExpiry] = useState('');
  const [broadcastPickupStart, setBroadcastPickupStart] = useState('');
  const [broadcastPickupEnd, setBroadcastPickupEnd] = useState('');
  const [broadcastAllergens, setBroadcastAllergens] = useState('');
  const [selectedBatchId, setSelectedBatchId] = useState<string>('');

  // Data queries & mutations
  const { data: listings = [], isLoading } = useSurplusListings();
  const { data: batches = [] } = useBatches();
  const createListingMutation = useCreateSurplusListing();
  const deleteListingMutation = useDeleteSurplusListing();
  const createRequestMutation = useCreateDonationRequest();
  const notifyMatchesMutation = useNotifyListingMatches();

  const { data: matchesData, isLoading: isMatchesLoading } = useListingMatches(
    selectedListingForMatches?.id || 0
  );

  const matches: MatchingResultItem[] = useMemo(() => {
    return matchesData?.matches || [];
  }, [matchesData]);

  // Auto-fill broadcast from batch selection
  const handleBatchSelect = (batchIdStr: string) => {
    setSelectedBatchId(batchIdStr);
    if (!batchIdStr) return;
    const b = batches.find((item) => String(item.id) === batchIdStr);
    if (b) {
      setBroadcastTitle(b.product_name || `Batch #${b.id}`);
      setBroadcastQty(String(b.quantity || '10'));
      setBroadcastUnit(b.unit || 'kg');
      if (b.expiry_date) {
        setBroadcastExpiry(`${b.expiry_date}T18:00`);
      }
      if (b.category) {
        const catUpper = b.category.toUpperCase().replace(/\s+/g, '_');
        if (CATEGORIES.includes(catUpper)) {
          setBroadcastCategory(catUpper);
        }
      }
    }
  };

  // Filtered listings
  const filteredListings = useMemo(() => {
    return listings.filter((item) => {
      // Search
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesTitle = item.title.toLowerCase().includes(q);
        const matchesDonor = item.donor_name.toLowerCase().includes(q);
        const matchesCategory = item.food_category.toLowerCase().includes(q);
        const matchesDesc = item.description?.toLowerCase().includes(q);
        if (!matchesTitle && !matchesDonor && !matchesCategory && !matchesDesc) {
          return false;
        }
      }

      // Status
      if (statusFilter !== 'ALL' && item.status !== statusFilter) {
        return false;
      }

      // Category
      if (selectedCategory !== 'ALL' && item.food_category.toUpperCase() !== selectedCategory) {
        return false;
      }

      // Temperature
      if (temperatureFilter !== 'ALL' && item.temperature_control !== temperatureFilter) {
        return false;
      }

      // Cooked
      if (cookedOnly && !item.is_cooked) {
        return false;
      }

      return true;
    });
  }, [listings, searchQuery, statusFilter, selectedCategory, temperatureFilter, cookedOnly]);

  // Request Donation Submit
  const handleRequestSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedListingForRequest) return;

    const qty = Number(requestedQty);
    const maxQty = Number(selectedListingForRequest.available_quantity);
    if (!qty || qty <= 0 || qty > maxQty) {
      onTriggerToast?.(`Please enter a quantity between 1 and ${maxQty} ${selectedListingForRequest.unit}`);
      return;
    }

    if (!requestedPickupTime) {
      onTriggerToast?.('Please specify a requested pickup date and time');
      return;
    }

    createRequestMutation.mutate(
      {
        listing: selectedListingForRequest.id,
        item_name: selectedListingForRequest.title,
        requested_quantity: qty,
        requested_pickup_time: requestedPickupTime,
        pickup_notes: pickupNotes,
      },
      {
        onSuccess: () => {
          onTriggerToast?.(`Donation request submitted for "${selectedListingForRequest.title}"!`);
          setSelectedListingForRequest(null);
          setRequestedQty('');
          setRequestedPickupTime('');
          setPickupNotes('');
          if (onNavigate) {
            onNavigate('donations');
          }
        },
        onError: (err: unknown) => {
          const msg = err instanceof Error ? err.message : 'Failed to submit donation request';
          onTriggerToast?.(msg);
        },
      }
    );
  };

  // Broadcast Listing Submit
  const handleBroadcastSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!broadcastTitle || !broadcastQty || !broadcastExpiry) {
      onTriggerToast?.('Please fill out all required fields: title, quantity, and expiry date');
      return;
    }

    const payload: Partial<SurplusListingItem> = {
      title: broadcastTitle,
      description: broadcastDesc,
      food_category: broadcastCategory,
      quantity_offered: Number(broadcastQty),
      unit: broadcastUnit,
      temperature_control: broadcastTemp,
      is_cooked: broadcastIsCooked,
      expiry_date: broadcastExpiry,
      pickup_start: broadcastPickupStart || new Date().toISOString(),
      pickup_end: broadcastPickupEnd || broadcastExpiry,
      allergens: broadcastAllergens
        ? broadcastAllergens.split(',').map((s) => s.trim()).filter(Boolean)
        : [],
      batch: selectedBatchId ? Number(selectedBatchId) : null,
    };

    createListingMutation.mutate(payload, {
      onSuccess: () => {
        onTriggerToast?.(`Surplus listing "${broadcastTitle}" broadcasted to NGO partners!`);
        setIsBroadcastOpen(false);
        setBroadcastTitle('');
        setBroadcastDesc('');
        setBroadcastQty('');
        setBroadcastExpiry('');
        setBroadcastPickupStart('');
        setBroadcastPickupEnd('');
        setBroadcastAllergens('');
        setSelectedBatchId('');
      },
      onError: (err: unknown) => {
        const msg = err instanceof Error ? err.message : 'Failed to broadcast surplus listing';
        onTriggerToast?.(msg);
      },
    });
  };

  // Notify matches
  const handleNotifyMatches = () => {
    if (!selectedListingForMatches) return;
    notifyMatchesMutation.mutate(
      { listingId: selectedListingForMatches.id },
      {
        onSuccess: () => {
          onTriggerToast?.(`Broadcasted instant match notifications to ${matches.length} compatible NGOs!`);
        },
        onError: (err: unknown) => {
          const msg = err instanceof Error ? err.message : 'Failed to dispatch match notifications';
          onTriggerToast?.(msg);
        },
      }
    );
  };

  // Status mapping for badge
  const getStatusBadgeProps = (status: SurplusListingStatus): { variant: StatusVariant; label: string } => {
    switch (status) {
      case 'AVAILABLE':
        return { variant: 'success', label: 'Available' };
      case 'PARTIALLY_RESERVED':
        return { variant: 'warning', label: 'Partially Reserved' };
      case 'CLAIMED':
        return { variant: 'info', label: 'Fully Claimed' };
      case 'EXPIRED':
        return { variant: 'danger', label: 'Expired' };
      case 'CANCELLED':
        return { variant: 'neutral', label: 'Cancelled' };
      default:
        return { variant: 'neutral', label: status };
    }
  };

  // Temperature icon
  const getTempIcon = (temp: 'AMBIENT' | 'CHILLED' | 'FROZEN') => {
    switch (temp) {
      case 'FROZEN':
        return <Snowflake className="w-3 h-3 text-cyan-400 shrink-0" />;
      case 'CHILLED':
        return <Thermometer className="w-3 h-3 text-blue-400 shrink-0" />;
      default:
        return <Sun className="w-3 h-3 text-amber-400 shrink-0" />;
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-150">
      {/* Page Header */}
      <PageHeader
        title="Surplus Marketplace"
        subtitle="Explore active surplus food donations, connect directly with donors, and rescue perishables."
        action={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onNavigate?.('donations')}
              className="text-xs"
            >
              Donation Requests
            </Button>
            {isBusiness ? (
              <Button
                variant="primary"
                size="sm"
                onClick={() => setIsBroadcastOpen(true)}
                className="text-xs font-semibold"
              >
                <Plus className="w-4 h-4" />
                <span>Broadcast Surplus</span>
              </Button>
            ) : (
              <Button
                variant="primary"
                size="sm"
                onClick={() => onNavigate?.('requirements')}
                className="text-xs font-semibold"
              >
                <Plus className="w-4 h-4" />
                <span>Post Requirement</span>
              </Button>
            )}
          </div>
        }
      />

      {/* Filter and Search Bar */}
      <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-4 shadow-2xs space-y-3.5">
        <div className="flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
          {/* Search Box */}
          <div className="relative flex-1">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted)]" />
            <input
              type="text"
              placeholder="Search by food item, donor restaurant/hotel, category, or allergen..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] pl-9.5 pr-4 py-2 text-xs text-[var(--text)] placeholder-[var(--muted)] focus:outline-none focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)] transition-all"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--muted)] hover:text-[var(--text)]"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Quick Filters */}
          <div className="flex items-center gap-2 flex-wrap">
            {/* Cooked meals toggle */}
            <button
              type="button"
              onClick={() => setCookedOnly(!cookedOnly)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] text-xs font-medium border transition-colors cursor-pointer ${
                cookedOnly
                  ? 'border-[var(--color-warning)] bg-[var(--color-warning-subtle)] text-[var(--color-warning)] shadow-2xs'
                  : 'border-[var(--border)] bg-[var(--surface-2)] text-[var(--muted)] hover:text-[var(--text)]'
              }`}
            >
              <Flame className="w-3.5 h-3.5 text-amber-500" />
              <span>Cooked Meals</span>
            </button>

            {/* Temperature filter */}
            <div className="flex items-center rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-0.5">
              {(['ALL', 'AMBIENT', 'CHILLED', 'FROZEN'] as const).map((temp) => (
                <button
                  key={temp}
                  type="button"
                  onClick={() => setTemperatureFilter(temp)}
                  className={`px-2 py-1 text-[11px] font-semibold rounded-[6px] capitalize transition-colors cursor-pointer ${
                    temperatureFilter === temp
                      ? 'bg-[var(--surface)] text-[var(--text)] shadow-2xs'
                      : 'text-[var(--muted)] hover:text-[var(--text)]'
                  }`}
                >
                  {temp === 'ALL' ? 'All Temp' : temp.toLowerCase()}
                </button>
              ))}
            </div>

            {/* View Mode Toggle */}
            <div className="flex items-center rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-0.5">
              <button
                type="button"
                onClick={() => setViewMode('grid')}
                className={`p-1.5 rounded-[6px] transition-colors cursor-pointer ${
                  viewMode === 'grid'
                    ? 'bg-[var(--surface)] text-[var(--text)] shadow-2xs'
                    : 'text-[var(--muted)] hover:text-[var(--text)]'
                }`}
                title="Grid View"
              >
                <LayoutGrid className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={() => setViewMode('table')}
                className={`p-1.5 rounded-[6px] transition-colors cursor-pointer ${
                  viewMode === 'table'
                    ? 'bg-[var(--surface)] text-[var(--text)] shadow-2xs'
                    : 'text-[var(--muted)] hover:text-[var(--text)]'
                }`}
                title="Table View"
              >
                <List className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>

        {/* Categories Bar */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 pt-1 no-scrollbar">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => setSelectedCategory(cat)}
              className={`px-2.5 py-1 rounded-[6px] text-[11px] font-semibold whitespace-nowrap transition-all cursor-pointer ${
                selectedCategory === cat
                  ? 'bg-[var(--primary)] text-[var(--primary-foreground)] shadow-2xs'
                  : 'bg-[var(--surface-2)] text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--surface-3,var(--border))]'
              }`}
            >
              {cat === 'ALL' ? 'All Categories' : cat.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content: Grid or Table */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <Skeleton variant="card" />
          <Skeleton variant="card" />
          <Skeleton variant="card" />
        </div>
      ) : filteredListings.length === 0 ? (
        <EmptyState
          icon={Store}
          title="No surplus food listings match your filters"
          description="Try broadening your search keywords, clearing category filters, or check back shortly for newly broadcasted batches."
          action={
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setSearchQuery('');
                setSelectedCategory('ALL');
                setStatusFilter('ALL');
                setCookedOnly(false);
                setTemperatureFilter('ALL');
              }}
            >
              Reset Filters
            </Button>
          }
        />
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredListings.map((item) => {
            const statusBadge = getStatusBadgeProps(item.status);
            const availQty = Number(item.available_quantity);
            const totalQty = Number(item.quantity_offered) || 1;
            const pct = Math.max(0, Math.min(100, Math.round((availQty / totalQty) * 100)));
            const isOwner = user?.organization?.name === item.donor_name;
            const canRequest = availQty > 0 && item.status !== 'EXPIRED' && item.status !== 'CLAIMED' && !isOwner;

            return (
              <div
                key={item.id}
                className="group flex flex-col justify-between rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-4 shadow-2xs hover:shadow-md hover:border-[var(--primary)]/40 transition-all duration-200"
              >
                <div className="space-y-3">
                  {/* Top Row: Category & Badges */}
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="px-2 py-0.5 rounded-[4px] text-[10px] font-bold uppercase tracking-wide bg-[var(--surface-2)] text-[var(--muted)] border border-[var(--border)]">
                        {item.food_category.replace('_', ' ')}
                      </span>
                      {item.is_cooked && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[4px] text-[10px] font-semibold bg-amber-500/10 text-amber-500 border border-amber-500/20">
                          <Flame className="w-2.5 h-2.5" />
                          Cooked
                        </span>
                      )}
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-[4px] text-[10px] font-medium bg-[var(--surface-2)] text-[var(--muted)] border border-[var(--border)]">
                        {getTempIcon(item.temperature_control)}
                        <span className="capitalize">{item.temperature_control.toLowerCase()}</span>
                      </span>
                    </div>
                    <StatusBadge variant={statusBadge.variant}>{statusBadge.label}</StatusBadge>
                  </div>

                  {/* Title & Description */}
                  <div>
                    <h3 className="text-sm font-bold text-[var(--text)] group-hover:text-[var(--primary)] transition-colors line-clamp-1">
                      {item.title}
                    </h3>
                    <p className="text-xs text-[var(--muted)] mt-1 line-clamp-2 leading-relaxed">
                      {item.description || 'Nutritious surplus inventory available for certified relief distribution.'}
                    </p>
                  </div>

                  {/* Donor & Location */}
                  <div className="rounded-[8px] bg-[var(--surface-2)]/60 p-2.5 space-y-1.5 border border-[var(--border)]">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <Building2 className="w-3.5 h-3.5 text-[var(--muted)] shrink-0" />
                        <span className="text-xs font-semibold text-[var(--text)] truncate">
                          {item.donor_name}
                        </span>
                      </div>
                      {item.donor_rating && (
                        <div className="flex items-center gap-1 shrink-0">
                          <RatingStars rating={item.donor_rating} />
                          <span className="text-[10px] font-bold text-[var(--text)]">
                            {item.donor_rating.toFixed(1)}
                          </span>
                        </div>
                      )}
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-[var(--muted)]">
                      <div className="flex items-center gap-1 truncate">
                        <MapPin className="w-3 h-3 shrink-0" />
                        <span className="truncate">{item.donor_address || 'Central Facility'}</span>
                      </div>
                      {item.distance_km !== undefined && (
                        <span className="shrink-0 font-medium text-[var(--primary)]">
                          {item.distance_km.toFixed(1)} km
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Quantity & Inventory Meter */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-[var(--muted)]">Available Surplus:</span>
                      <span className="font-bold text-[var(--text)] tabular-nums">
                        {availQty} / {item.quantity_offered} {item.unit}
                      </span>
                    </div>
                    <div className="h-1.5 w-full rounded-full bg-[var(--surface-2)] overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-300 ${
                          pct > 50
                            ? 'bg-[var(--color-success)]'
                            : pct > 20
                            ? 'bg-[var(--color-warning)]'
                            : 'bg-[var(--color-danger)]'
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>

                  {/* Expiry & Pickup Timers */}
                  <div className="flex items-center justify-between text-[11px] pt-1 border-t border-[var(--border)]">
                    <div className="flex items-center gap-1 text-[var(--muted)]">
                      <Clock className="w-3 h-3 text-[var(--muted)] shrink-0" />
                      <span>Expires:</span>
                    </div>
                    <span className="font-semibold text-[var(--text)] tabular-nums">
                      {new Date(item.expiry_date).toLocaleDateString([], {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  </div>

                  {/* Allergens pill list */}
                  {item.allergens && item.allergens.length > 0 && (
                    <div className="flex items-center gap-1 flex-wrap pt-0.5">
                      <span className="text-[10px] text-[var(--muted)]">Contains:</span>
                      {item.allergens.map((alg) => (
                        <span
                          key={alg}
                          className="px-1.5 py-0.2 rounded text-[9px] font-semibold bg-[var(--color-danger-subtle)] text-[var(--color-danger)]"
                        >
                          {alg}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Bottom Actions */}
                <div className="pt-4 mt-3 border-t border-[var(--border)] flex items-center gap-2">
                  {isOwner ? (
                    <>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setSelectedListingForMatches(item)}
                        className="flex-1 text-xs"
                      >
                        <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                        <span>Find Matches</span>
                      </Button>
                      <button
                        type="button"
                        onClick={() => {
                          if (confirm(`Cancel listing "${item.title}"?`)) {
                            deleteListingMutation.mutate(item.id, {
                              onSuccess: () => onTriggerToast?.('Surplus listing cancelled'),
                            });
                          }
                        }}
                        className="p-2 rounded-[8px] border border-[var(--border)] text-[var(--muted)] hover:text-[var(--color-danger)] hover:bg-[var(--surface-2)] transition-colors cursor-pointer"
                        title="Delete listing"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </>
                  ) : (
                    <Button
                      variant={canRequest ? 'primary' : 'outline'}
                      size="sm"
                      disabled={!canRequest}
                      onClick={() => {
                        setSelectedListingForRequest(item);
                        setRequestedQty(String(availQty));
                      }}
                      className="w-full text-xs font-semibold"
                    >
                      <ArrowRight className="w-3.5 h-3.5" />
                      <span>{availQty <= 0 ? 'Fully Claimed' : 'Request Donation'}</span>
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* Table View */
        <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] overflow-hidden shadow-2xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-[var(--border)] bg-[var(--surface-2)] text-[var(--muted)] font-semibold">
                  <th className="py-3 px-4">Item & Category</th>
                  <th className="py-3 px-4">Donor Organization</th>
                  <th className="py-3 px-4">Available Qty</th>
                  <th className="py-3 px-4">Storage & Temp</th>
                  <th className="py-3 px-4">Expiry Date</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {filteredListings.map((item) => {
                  const statusBadge = getStatusBadgeProps(item.status);
                  const availQty = Number(item.available_quantity);
                  const isOwner = user?.organization?.name === item.donor_name;
                  const canRequest = availQty > 0 && item.status !== 'EXPIRED' && !isOwner;

                  return (
                    <tr
                      key={item.id}
                      className="hover:bg-[var(--surface-2)]/60 transition-colors"
                    >
                      <td className="py-3 px-4">
                        <div className="font-semibold text-[var(--text)]">{item.title}</div>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <span className="text-[10px] text-[var(--muted)] uppercase font-semibold">
                            {item.food_category.replace('_', ' ')}
                          </span>
                          {item.is_cooked && (
                            <span className="text-[10px] text-amber-500 font-semibold flex items-center gap-0.5">
                              • <Flame className="w-2.5 h-2.5 inline" /> Cooked
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <div className="font-medium text-[var(--text)]">{item.donor_name}</div>
                        <div className="text-[11px] text-[var(--muted)] truncate max-w-[180px]">
                          {item.donor_address || 'Central Hub'}
                        </div>
                      </td>
                      <td className="py-3 px-4 font-semibold text-[var(--text)] tabular-nums">
                        {availQty} / {item.quantity_offered} {item.unit}
                      </td>
                      <td className="py-3 px-4">
                        <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[4px] text-[10px] font-medium bg-[var(--surface-2)] border border-[var(--border)]">
                          {getTempIcon(item.temperature_control)}
                          <span className="capitalize">{item.temperature_control.toLowerCase()}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-[11px] text-[var(--text)] tabular-nums">
                        {new Date(item.expiry_date).toLocaleDateString([], {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </td>
                      <td className="py-3 px-4">
                        <StatusBadge variant={statusBadge.variant}>{statusBadge.label}</StatusBadge>
                      </td>
                      <td className="py-3 px-4 text-right">
                        {isOwner ? (
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => setSelectedListingForMatches(item)}
                            className="text-xs"
                          >
                            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                            <span>Matches</span>
                          </Button>
                        ) : (
                          <Button
                            variant={canRequest ? 'primary' : 'outline'}
                            size="sm"
                            disabled={!canRequest}
                            onClick={() => {
                              setSelectedListingForRequest(item);
                              setRequestedQty(String(availQty));
                            }}
                            className="text-xs"
                          >
                            Request
                          </Button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* MODAL 1: Request Donation Modal */}
      {selectedListingForRequest && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in"
        >
          <div className="w-full max-w-lg rounded-[16px] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl space-y-5 animate-in zoom-in-95 duration-150">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-base font-bold text-[var(--text)]">Request Food Donation</h3>
                <p className="text-xs text-[var(--muted)] mt-0.5">
                  Reserve surplus stock directly from {selectedListingForRequest.donor_name}.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedListingForRequest(null)}
                className="p-1 rounded-[6px] text-[var(--muted)] hover:text-[var(--text)]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Listing Summary Box */}
            <div className="rounded-[10px] bg-[var(--surface-2)] p-3 border border-[var(--border)] space-y-1.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-[var(--text)]">
                  {selectedListingForRequest.title}
                </span>
                <span className="text-[var(--primary)] font-bold">
                  {selectedListingForRequest.available_quantity} {selectedListingForRequest.unit} available
                </span>
              </div>
              <p className="text-[11px] text-[var(--muted)]">
                Storage: {selectedListingForRequest.temperature_control.toLowerCase()} • Donor:{' '}
                {selectedListingForRequest.donor_name} ({selectedListingForRequest.donor_address || 'Facility'})
              </p>
            </div>

            <form onSubmit={handleRequestSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-[var(--text)]">
                  Requested Quantity ({selectedListingForRequest.unit}) *
                </label>
                <input
                  type="number"
                  required
                  min={1}
                  max={Number(selectedListingForRequest.available_quantity)}
                  step="any"
                  value={requestedQty}
                  onChange={(e) => setRequestedQty(e.target.value)}
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--text)] focus:outline-none focus:border-[var(--primary)]"
                  placeholder={`Enter quantity up to ${selectedListingForRequest.available_quantity}`}
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-[var(--text)]">
                  Preferred Pickup Window *
                </label>
                <input
                  type="datetime-local"
                  required
                  value={requestedPickupTime}
                  onChange={(e) => setRequestedPickupTime(e.target.value)}
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--text)] focus:outline-none focus:border-[var(--primary)]"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-[var(--text)]">
                  Transportation & Handling Notes
                </label>
                <textarea
                  rows={3}
                  value={pickupNotes}
                  onChange={(e) => setPickupNotes(e.target.value)}
                  placeholder="e.g., Volunteer van with refrigerated cold storage bag arriving at back loading dock."
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--text)] focus:outline-none focus:border-[var(--primary)] resize-none"
                />
              </div>

              <div className="pt-2 flex items-center justify-end gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  type="button"
                  onClick={() => setSelectedListingForRequest(null)}
                >
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  type="submit"
                  disabled={createRequestMutation.isPending}
                >
                  {createRequestMutation.isPending ? 'Reserving...' : 'Submit Request'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: Broadcast Surplus Modal */}
      {isBroadcastOpen && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in"
        >
          <div className="w-full max-w-xl max-h-[90vh] overflow-y-auto rounded-[16px] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl space-y-5 animate-in zoom-in-95 duration-150">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-base font-bold text-[var(--text)]">Broadcast Food Surplus</h3>
                <p className="text-xs text-[var(--muted)] mt-0.5">
                  Publish expiring batches to certified NGO distribution partners for immediate rescue.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsBroadcastOpen(false)}
                className="p-1 rounded-[6px] text-[var(--muted)] hover:text-[var(--text)]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Quick pre-fill from inventory batch */}
            {batches.length > 0 && (
              <div className="rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-3 space-y-1.5">
                <label className="text-[11px] font-semibold text-[var(--muted)]">
                  Fast Autofill from Active Inventory Batch:
                </label>
                <select
                  value={selectedBatchId}
                  onChange={(e) => handleBatchSelect(e.target.value)}
                  className="w-full rounded-[6px] border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1.5 text-xs text-[var(--text)] focus:outline-none focus:border-[var(--primary)]"
                >
                  <option value="">-- Choose inventory batch (optional) --</option>
                  {batches.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.product_name} • Batch #{b.id} ({b.quantity} {b.unit} left, exp {b.expiry_date})
                    </option>
                  ))}
                </select>
              </div>
            )}

            <form onSubmit={handleBroadcastSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-[var(--text)]">
                  Food Item Title *
                </label>
                <input
                  type="text"
                  required
                  value={broadcastTitle}
                  onChange={(e) => setBroadcastTitle(e.target.value)}
                  placeholder="e.g. Fresh Artisan Sourdough Loaves & Croissants"
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--text)] focus:outline-none focus:border-[var(--primary)]"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-[var(--text)]">
                    Food Category *
                  </label>
                  <select
                    value={broadcastCategory}
                    onChange={(e) => setBroadcastCategory(e.target.value)}
                    className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--text)] focus:outline-none focus:border-[var(--primary)]"
                  >
                    {CATEGORIES.filter((c) => c !== 'ALL').map((cat) => (
                      <option key={cat} value={cat}>
                        {cat.replace('_', ' ')}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-[var(--text)]">
                    Temperature Control *
                  </label>
                  <select
                    value={broadcastTemp}
                    onChange={(e) => setBroadcastTemp(e.target.value as 'AMBIENT' | 'CHILLED' | 'FROZEN')}
                    className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--text)] focus:outline-none focus:border-[var(--primary)]"
                  >
                    <option value="AMBIENT">Ambient (Room Temp)</option>
                    <option value="CHILLED">Chilled / Refrigerated (0-4°C)</option>
                    <option value="FROZEN">Frozen (&lt; -18°C)</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-[var(--text)]">
                    Quantity Offered *
                  </label>
                  <input
                    type="number"
                    required
                    min={0.1}
                    step="any"
                    value={broadcastQty}
                    onChange={(e) => setBroadcastQty(e.target.value)}
                    placeholder="e.g. 25"
                    className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--text)] focus:outline-none focus:border-[var(--primary)]"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-[var(--text)]">Unit</label>
                  <select
                    value={broadcastUnit}
                    onChange={(e) => setBroadcastUnit(e.target.value)}
                    className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--text)] focus:outline-none focus:border-[var(--primary)]"
                  >
                    <option value="kg">kg (Kilograms)</option>
                    <option value="portions">portions</option>
                    <option value="boxes">boxes</option>
                    <option value="litres">litres</option>
                    <option value="units">units</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-[var(--text)]">
                    Expiry / Best Before *
                  </label>
                  <input
                    type="datetime-local"
                    required
                    value={broadcastExpiry}
                    onChange={(e) => setBroadcastExpiry(e.target.value)}
                    className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--text)] focus:outline-none focus:border-[var(--primary)]"
                  />
                </div>

                <div className="space-y-1.5 flex items-center pt-6">
                  <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-[var(--text)]">
                    <input
                      type="checkbox"
                      checked={broadcastIsCooked}
                      onChange={(e) => setBroadcastIsCooked(e.target.checked)}
                      className="rounded border-[var(--border)] text-[var(--primary)] focus:ring-[var(--primary)] w-4 h-4"
                    />
                    <span>Cooked / Prepared Meal</span>
                  </label>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-[var(--text)]">
                  Allergens (comma separated)
                </label>
                <input
                  type="text"
                  value={broadcastAllergens}
                  onChange={(e) => setBroadcastAllergens(e.target.value)}
                  placeholder="e.g. Gluten, Dairy, Nuts"
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--text)] focus:outline-none focus:border-[var(--primary)]"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-[var(--text)]">Description & Packaging</label>
                <textarea
                  rows={2}
                  value={broadcastDesc}
                  onChange={(e) => setBroadcastDesc(e.target.value)}
                  placeholder="e.g. Baked this morning at 6 AM. Cleanly packaged in food-grade kraft containers."
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--text)] focus:outline-none focus:border-[var(--primary)] resize-none"
                />
              </div>

              <div className="pt-2 flex items-center justify-end gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  type="button"
                  onClick={() => setIsBroadcastOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  type="submit"
                  disabled={createListingMutation.isPending}
                >
                  {createListingMutation.isPending ? 'Publishing...' : 'Broadcast to Marketplace'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DRAWER: Compatible NGO Matches Drawer */}
      {selectedListingForMatches && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-xs animate-in fade-in"
        >
          <div className="w-full max-w-md h-full bg-[var(--surface)] border-l border-[var(--border)] p-6 flex flex-col justify-between shadow-2xl animate-in slide-in-from-right duration-200">
            <div className="space-y-5">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4 text-amber-500" />
                    <h3 className="text-base font-bold text-[var(--text)]">Compatible NGO Matches</h3>
                  </div>
                  <p className="text-xs text-[var(--muted)] mt-1">
                    Matched requirements for "{selectedListingForMatches.title}"
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedListingForMatches(null)}
                  className="p-1 rounded-[6px] text-[var(--muted)] hover:text-[var(--text)]"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="space-y-3 overflow-y-auto max-h-[calc(100vh-220px)] pr-1">
                {isMatchesLoading ? (
                  <div className="space-y-2">
                    <Skeleton variant="card" />
                    <Skeleton variant="card" />
                  </div>
                ) : matches.length === 0 ? (
                  <div className="text-center py-10 space-y-2">
                    <Package className="w-8 h-8 text-[var(--muted)] mx-auto" />
                    <p className="text-xs text-[var(--text)] font-semibold">No active matching requirements</p>
                    <p className="text-[11px] text-[var(--muted)]">
                      SurplusSync automatically notifies NGOs in real-time when new requirements are posted.
                    </p>
                  </div>
                ) : (
                  matches.map((m: MatchingResultItem, idx: number) => (
                    <div
                      key={idx}
                      className="rounded-[10px] border border-[var(--border)] bg-[var(--surface-2)] p-3 space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-xs text-[var(--text)]">
                          {m.requirement?.ngo_name || 'Relief Partner'}
                        </span>
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[var(--color-success-subtle)] text-[var(--color-success)] border border-[var(--color-success-border)]">
                          {Math.round(m.match_score)}% Match
                        </span>
                      </div>

                      <div className="text-[11px] text-[var(--muted)] space-y-1">
                        <div>Requirement: {m.requirement?.title}</div>
                        <div className="flex items-center justify-between">
                          <span>Target: {m.requirement?.target_beneficiaries} beneficiaries</span>
                          {m.distance_km !== undefined && (
                            <span className="font-medium text-[var(--text)]">
                              {m.distance_km.toFixed(1)} km away
                            </span>
                          )}
                        </div>
                      </div>

                      {m.reasons && m.reasons.length > 0 && (
                        <div className="pt-2 border-t border-[var(--border)] space-y-1 text-[10px] text-[var(--muted)]">
                          {m.reasons.map((reason, rIdx) => (
                            <div key={rIdx} className="flex items-start gap-1 leading-snug">
                              <span className="text-[var(--primary)] font-bold shrink-0">•</span>
                              <span>{reason}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>

            {matches.length > 0 && (
              <div className="pt-4 border-t border-[var(--border)]">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleNotifyMatches}
                  disabled={notifyMatchesMutation.isPending}
                  className="w-full text-xs font-semibold"
                >
                  <Bell className="w-3.5 h-3.5" />
                  <span>{notifyMatchesMutation.isPending ? 'Sending...' : 'Dispatch Alert to Matched NGOs'}</span>
                </Button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

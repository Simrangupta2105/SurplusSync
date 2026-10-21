import React, { useState, useMemo } from 'react';
import {
  Heart,
  Plus,
  Search,
  AlertTriangle,
  Sparkles,
  Users,
  Package,
  X,
  Trash2,
  ArrowRight,
} from 'lucide-react';
import { PageHeader } from '../components/ui/PageHeader';
import { Button } from '../components/ui/Button';
import { StatusBadge, type StatusVariant } from '../components/ui/StatusBadge';
import { EmptyState } from '../components/ui/EmptyState';
import { Skeleton } from '../components/ui/Skeleton';
import {
  useNGORequirements,
  useCreateNGORequirement,
  useDeleteNGORequirement,
  useRequirementMatches,
  useCreateDonationRequest,
  useCurrentUser,
} from '../hooks/useData';
import type {
  NGORequirementItem,
  NGORequirementStatus,
  MatchingResultItem,
} from '../types';

interface NgoRequirementsPageProps {
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

export const NgoRequirementsPage: React.FC<NgoRequirementsPageProps> = ({
  onTriggerToast,
  onNavigate,
}) => {
  const { data: user } = useCurrentUser();

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | NGORequirementStatus>('ALL');
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [urgentOnly, setUrgentOnly] = useState(false);

  // Modals state
  const [isPostOpen, setIsPostOpen] = useState(false);
  const [selectedReqForMatches, setSelectedReqForMatches] = useState<NGORequirementItem | null>(null);

  // Form: Post Requirement
  const [postTitle, setPostTitle] = useState('');
  const [postCategory, setPostCategory] = useState('PRODUCE');
  const [postMinKg, setPostMinKg] = useState('');
  const [postBeneficiaries, setPostBeneficiaries] = useState('');
  const [postIsUrgent, setPostIsUrgent] = useState(false);
  const [postNeededBy, setPostNeededBy] = useState('');
  const [postNotes, setPostNotes] = useState('');

  // Data queries & mutations
  const { data: requirements = [], isLoading } = useNGORequirements();
  const createReqMutation = useCreateNGORequirement();
  const deleteReqMutation = useDeleteNGORequirement();
  const createDonationReqMutation = useCreateDonationRequest();

  const { data: matchesData, isLoading: isMatchesLoading } = useRequirementMatches(
    selectedReqForMatches?.id || 0
  );

  const matches: MatchingResultItem[] = useMemo(() => {
    return matchesData?.matches || [];
  }, [matchesData]);

  // Filter logic
  const filteredRequirements = useMemo(() => {
    return requirements.filter((item) => {
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesTitle = item.title.toLowerCase().includes(q);
        const matchesNgo = item.ngo_name.toLowerCase().includes(q);
        const matchesNotes = item.notes?.toLowerCase().includes(q);
        if (!matchesTitle && !matchesNgo && !matchesNotes) return false;
      }
      if (statusFilter !== 'ALL' && item.fulfillment_status !== statusFilter) {
        return false;
      }
      if (categoryFilter !== 'ALL' && item.food_category.toUpperCase() !== categoryFilter) {
        return false;
      }
      if (urgentOnly && !item.is_urgent) {
        return false;
      }
      return true;
    });
  }, [requirements, searchQuery, statusFilter, categoryFilter, urgentOnly]);

  // Submit Post Requirement
  const handlePostSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!postTitle || !postMinKg || !postNeededBy) {
      onTriggerToast?.('Please fill out all required fields');
      return;
    }

    createReqMutation.mutate(
      {
        title: postTitle,
        food_category: postCategory,
        min_quantity_kg: Number(postMinKg),
        target_beneficiaries: Number(postBeneficiaries) || 50,
        is_urgent: postIsUrgent,
        needed_by: postNeededBy,
        notes: postNotes,
        fulfillment_status: 'OPEN',
      },
      {
        onSuccess: () => {
          onTriggerToast?.(`Requirement "${postTitle}" published to donor network!`);
          setIsPostOpen(false);
          setPostTitle('');
          setPostMinKg('');
          setPostBeneficiaries('');
          setPostIsUrgent(false);
          setPostNeededBy('');
          setPostNotes('');
        },
        onError: (err: unknown) => {
          const msg = err instanceof Error ? err.message : 'Failed to publish requirement';
          onTriggerToast?.(msg);
        },
      }
    );
  };

  // Status badge config
  const getStatusBadge = (status: NGORequirementStatus): { variant: StatusVariant; label: string } => {
    switch (status) {
      case 'OPEN':
        return { variant: 'success', label: 'Open' };
      case 'PARTIALLY_MET':
        return { variant: 'warning', label: 'Partially Met' };
      case 'FULFILLED':
        return { variant: 'info', label: 'Fulfilled' };
      case 'CLOSED':
        return { variant: 'neutral', label: 'Closed' };
      default:
        return { variant: 'neutral', label: status };
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-150">
      {/* Header */}
      <PageHeader
        title="NGO Food Requirements"
        subtitle="Express community relief demand and allow SurplusSync's engine to match donor surplus."
        action={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onNavigate?.('marketplace')}
              className="text-xs"
            >
              Surplus Marketplace
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => setIsPostOpen(true)}
              className="text-xs font-semibold"
            >
              <Plus className="w-4 h-4" />
              <span>Post Requirement</span>
            </Button>
          </div>
        }
      />

      {/* Filter Bar */}
      <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-4 shadow-2xs space-y-3.5">
        <div className="flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
          {/* Search Box */}
          <div className="relative flex-1">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted)]" />
            <input
              type="text"
              placeholder="Search requirements by beneficiary, title, or NGO name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] pl-9.5 pr-4 py-2 text-xs text-[var(--text)] placeholder-[var(--muted)] focus:outline-none focus:border-[var(--primary)]"
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
            <button
              type="button"
              onClick={() => setUrgentOnly(!urgentOnly)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] text-xs font-medium border transition-colors cursor-pointer ${
                urgentOnly
                  ? 'border-[var(--color-danger)] bg-[var(--color-danger-subtle)] text-[var(--color-danger)] shadow-2xs'
                  : 'border-[var(--border)] bg-[var(--surface-2)] text-[var(--muted)] hover:text-[var(--text)]'
              }`}
            >
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>Urgent Only</span>
            </button>

            {/* Status Pills */}
            <div className="flex items-center rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-0.5">
              {(['ALL', 'OPEN', 'PARTIALLY_MET', 'FULFILLED'] as const).map((st) => (
                <button
                  key={st}
                  type="button"
                  onClick={() => setStatusFilter(st)}
                  className={`px-2.5 py-1 text-[11px] font-semibold rounded-[6px] capitalize transition-colors cursor-pointer ${
                    statusFilter === st
                      ? 'bg-[var(--surface)] text-[var(--text)] shadow-2xs'
                      : 'text-[var(--muted)] hover:text-[var(--text)]'
                  }`}
                >
                  {st === 'ALL' ? 'All' : st.replace('_', ' ').toLowerCase()}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Categories Bar */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 pt-1 no-scrollbar">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => setCategoryFilter(cat)}
              className={`px-2.5 py-1 rounded-[6px] text-[11px] font-semibold whitespace-nowrap transition-all cursor-pointer ${
                categoryFilter === cat
                  ? 'bg-[var(--primary)] text-[var(--primary-foreground)] shadow-2xs'
                  : 'bg-[var(--surface-2)] text-[var(--muted)] hover:text-[var(--text)]'
              }`}
            >
              {cat === 'ALL' ? 'All Categories' : cat.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Main Grid List */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <Skeleton variant="card" />
          <Skeleton variant="card" />
          <Skeleton variant="card" />
        </div>
      ) : filteredRequirements.length === 0 ? (
        <EmptyState
          icon={Heart}
          title="No food requirements match your filter criteria"
          description="Click 'Post Requirement' to specify the food categories and target volumes your community relief program needs."
          action={
            <Button variant="primary" size="sm" onClick={() => setIsPostOpen(true)}>
              Post First Requirement
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredRequirements.map((item) => {
            const badge = getStatusBadge(item.fulfillment_status);
            const isOwner = user?.organization?.name === item.ngo_name;

            return (
              <div
                key={item.id}
                className="group flex flex-col justify-between rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-4 shadow-2xs hover:shadow-md hover:border-[var(--primary)]/40 transition-all duration-200"
              >
                <div className="space-y-3">
                  {/* Top Badges */}
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5">
                      <span className="px-2 py-0.5 rounded-[4px] text-[10px] font-bold uppercase tracking-wide bg-[var(--surface-2)] text-[var(--muted)] border border-[var(--border)]">
                        {item.food_category.replace('_', ' ')}
                      </span>
                      {item.is_urgent && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[4px] text-[10px] font-bold bg-[var(--color-danger-subtle)] text-[var(--color-danger)] border border-[var(--color-danger-border)] animate-pulse">
                          <AlertTriangle className="w-2.5 h-2.5" />
                          Urgent
                        </span>
                      )}
                    </div>
                    <StatusBadge variant={badge.variant}>{badge.label}</StatusBadge>
                  </div>

                  {/* Title & Notes */}
                  <div>
                    <h3 className="text-sm font-bold text-[var(--text)] group-hover:text-[var(--primary)] transition-colors line-clamp-1">
                      {item.title}
                    </h3>
                    <p className="text-xs text-[var(--muted)] mt-1 line-clamp-2 leading-relaxed">
                      {item.notes || 'Nutritional requirement for community shelter distribution.'}
                    </p>
                  </div>

                  {/* NGO Org Info */}
                  <div className="rounded-[8px] bg-[var(--surface-2)]/60 p-2.5 space-y-1.5 border border-[var(--border)]">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-[var(--text)] truncate">
                        {item.ngo_name}
                      </span>
                      <div className="flex items-center gap-1 text-[11px] text-[var(--muted)]">
                        <Users className="w-3 h-3 text-[var(--primary)]" />
                        <span className="font-semibold text-[var(--text)]">
                          {item.target_beneficiaries}
                        </span>
                        <span>served</span>
                      </div>
                    </div>
                  </div>

                  {/* Target kg & Needed by */}
                  <div className="space-y-1 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-[var(--muted)]">Min. Needed:</span>
                      <span className="font-bold text-[var(--text)] tabular-nums">
                        {item.min_quantity_kg} kg
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-[var(--muted)]">Needed By:</span>
                      <span className="font-semibold text-[var(--text)] tabular-nums">
                        {new Date(item.needed_by).toLocaleDateString([], {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="pt-4 mt-3 border-t border-[var(--border)] flex items-center gap-2">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => setSelectedReqForMatches(item)}
                    className="flex-1 text-xs font-semibold"
                  >
                    <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                    <span>View Matching Surplus</span>
                  </Button>
                  {isOwner && (
                    <button
                      type="button"
                      onClick={() => {
                        if (confirm(`Remove requirement "${item.title}"?`)) {
                          deleteReqMutation.mutate(item.id, {
                            onSuccess: () => onTriggerToast?.('Requirement removed'),
                          });
                        }
                      }}
                      className="p-2 rounded-[8px] border border-[var(--border)] text-[var(--muted)] hover:text-[var(--color-danger)] hover:bg-[var(--surface-2)] transition-colors cursor-pointer"
                      title="Delete requirement"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* MODAL: Post Requirement Modal */}
      {isPostOpen && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in"
        >
          <div className="w-full max-w-lg rounded-[16px] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl space-y-5 animate-in zoom-in-95 duration-150">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-base font-bold text-[var(--text)]">Post Food Relief Requirement</h3>
                <p className="text-xs text-[var(--muted)] mt-0.5">
                  Broadcast your community relief needs to local restaurants, caterers, and supermarkets.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsPostOpen(false)}
                className="p-1 rounded-[6px] text-[var(--muted)] hover:text-[var(--text)]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handlePostSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-[var(--text)]">
                  Requirement Title *
                </label>
                <input
                  type="text"
                  required
                  value={postTitle}
                  onChange={(e) => setPostTitle(e.target.value)}
                  placeholder="e.g. Daily Dinner Provision for 120 Shelter Residents"
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--text)] focus:outline-none focus:border-[var(--primary)]"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-[var(--text)]">
                    Food Category *
                  </label>
                  <select
                    value={postCategory}
                    onChange={(e) => setPostCategory(e.target.value)}
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
                    Min Quantity (kg) *
                  </label>
                  <input
                    type="number"
                    required
                    min={1}
                    step="any"
                    value={postMinKg}
                    onChange={(e) => setPostMinKg(e.target.value)}
                    placeholder="e.g. 30"
                    className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--text)] focus:outline-none focus:border-[var(--primary)]"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-[var(--text)]">
                    Target Beneficiaries Count
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={postBeneficiaries}
                    onChange={(e) => setPostBeneficiaries(e.target.value)}
                    placeholder="e.g. 150"
                    className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--text)] focus:outline-none focus:border-[var(--primary)]"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-[var(--text)]">
                    Needed By Date/Time *
                  </label>
                  <input
                    type="datetime-local"
                    required
                    value={postNeededBy}
                    onChange={(e) => setPostNeededBy(e.target.value)}
                    className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--text)] focus:outline-none focus:border-[var(--primary)]"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-[var(--text)] pt-1">
                  <input
                    type="checkbox"
                    checked={postIsUrgent}
                    onChange={(e) => setPostIsUrgent(e.target.checked)}
                    className="rounded border-[var(--border)] text-[var(--color-danger)] focus:ring-[var(--color-danger)] w-4 h-4"
                  />
                  <span className="font-semibold text-[var(--color-danger)]">
                    Flag as Urgent Relief Emergency
                  </span>
                </label>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-[var(--text)]">
                  Dietary Preferences & Handling Notes
                </label>
                <textarea
                  rows={3}
                  value={postNotes}
                  onChange={(e) => setPostNotes(e.target.value)}
                  placeholder="e.g. Halal or Vegetarian preferred. Must be ready-to-eat or easily microwaveable by 7 PM."
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--text)] focus:outline-none focus:border-[var(--primary)] resize-none"
                />
              </div>

              <div className="pt-2 flex items-center justify-end gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  type="button"
                  onClick={() => setIsPostOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  type="submit"
                  disabled={createReqMutation.isPending}
                >
                  {createReqMutation.isPending ? 'Publishing...' : 'Publish Requirement'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DRAWER: Matching Surplus Drawer */}
      {selectedReqForMatches && (
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
                    <h3 className="text-base font-bold text-[var(--text)]">Matching Surplus Listings</h3>
                  </div>
                  <p className="text-xs text-[var(--muted)] mt-1">
                    Direct matches found for "{selectedReqForMatches.title}"
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedReqForMatches(null)}
                  className="p-1 rounded-[6px] text-[var(--muted)] hover:text-[var(--text)]"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="space-y-3 overflow-y-auto max-h-[calc(100vh-180px)] pr-1">
                {isMatchesLoading ? (
                  <div className="space-y-2">
                    <Skeleton variant="card" />
                    <Skeleton variant="card" />
                  </div>
                ) : matches.length === 0 ? (
                  <div className="text-center py-12 space-y-2">
                    <Package className="w-8 h-8 text-[var(--muted)] mx-auto" />
                    <p className="text-xs font-semibold text-[var(--text)]">No current surplus matches</p>
                    <p className="text-[11px] text-[var(--muted)]">
                      SurplusSync will automatically notify your team when a compatible business listing becomes available.
                    </p>
                  </div>
                ) : (
                  matches.map((m: MatchingResultItem, idx: number) => {
                    const listing = m.listing;
                    if (!listing) return null;

                    return (
                      <div
                        key={idx}
                        className="rounded-[10px] border border-[var(--border)] bg-[var(--surface-2)] p-3.5 space-y-2.5"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-xs text-[var(--text)] truncate">
                            {listing.title}
                          </span>
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[var(--color-success-subtle)] text-[var(--color-success)] border border-[var(--color-success-border)] shrink-0">
                            {Math.round(m.match_score)}% Match
                          </span>
                        </div>

                        <div className="text-[11px] text-[var(--muted)] space-y-1">
                          <div className="flex items-center justify-between">
                            <span>Donor: {listing.donor_name}</span>
                            {m.distance_km !== undefined && (
                              <span className="font-medium text-[var(--primary)]">
                                {m.distance_km.toFixed(1)} km away
                              </span>
                            )}
                          </div>
                          <div className="flex items-center justify-between">
                            <span>
                              Available: {listing.available_quantity} {listing.unit}
                            </span>
                            <span>Exp: {new Date(listing.expiry_date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                          </div>
                        </div>

                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => {
                            createDonationReqMutation.mutate(
                              {
                                listing: listing.id,
                                item_name: listing.title,
                                requested_quantity: Math.min(
                                  Number(selectedReqForMatches.min_quantity_kg),
                                  Number(listing.available_quantity)
                                ),
                                requested_pickup_time: selectedReqForMatches.needed_by,
                                pickup_notes: `Matched from NGO requirement: ${selectedReqForMatches.title}`,
                              },
                              {
                                onSuccess: () => {
                                  onTriggerToast?.(`Donation requested from ${listing.donor_name}!`);
                                  setSelectedReqForMatches(null);
                                  onNavigate?.('donations');
                                },
                              }
                            );
                          }}
                          disabled={createDonationReqMutation.isPending}
                          className="w-full text-xs font-semibold"
                        >
                          <ArrowRight className="w-3.5 h-3.5" />
                          <span>Request Instant Rescue</span>
                        </Button>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            <div className="pt-4 border-t border-[var(--border)]">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedReqForMatches(null)}
                className="w-full text-xs"
              >
                Close Matches
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

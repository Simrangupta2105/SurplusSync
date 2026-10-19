import React, { useState } from 'react';
import {
  Star,
  EyeOff,
  Eye,
  Search,
  CheckCircle2,

  AlertTriangle,
  Building2,
  Users,
  MessageSquare,
  ShieldAlert,
} from 'lucide-react';
import { PageHeader } from '../../components/ui/PageHeader';
import { Button } from '../../components/ui/Button';
import { RatingStars } from '../../components/ui/RatingStars';
import { Skeleton } from '../../components/ui/Skeleton';
import { EmptyState } from '../../components/ui/EmptyState';
import {
  useAdminRatings,
  useHideRating,
  useUnhideRating,
} from '../../hooks/useData';
import type { AdminRating } from '../../types';

interface AdminRatingsPageProps {
  onTriggerToast?: (message: string) => void;
}

export const AdminRatingsPage: React.FC<AdminRatingsPageProps> = ({ onTriggerToast }) => {
  const [starFilter, setStarFilter] = useState<string>('ALL');
  const [hiddenFilter, setHiddenFilter] = useState<string>('ALL');
  const [search, setSearch] = useState('');

  // Moderation Dialog state
  const [modRating, setModRating] = useState<AdminRating | null>(null);
  const [modAction, setModAction] = useState<'HIDE' | 'UNHIDE' | null>(null);
  const [modReason, setModReason] = useState('');

  const { data: ratingsResponse, isLoading } = useAdminRatings({
    stars: starFilter === 'ALL' ? undefined : Number(starFilter),
    is_hidden:
      hiddenFilter === 'ALL' ? undefined : hiddenFilter === 'HIDDEN' ? true : false,
    search: search.trim() || undefined,
  });

  const hideMutation = useHideRating();
  const unhideMutation = useUnhideRating();

  const ratings = ratingsResponse?.results || [];

  const handleModeration = async () => {
    if (!modRating || !modAction) return;
    if (modAction === 'HIDE' && !modReason.trim()) {
      onTriggerToast?.('A reason is mandatory when hiding a review.');
      return;
    }

    try {
      if (modAction === 'HIDE') {
        await hideMutation.mutateAsync({
          id: modRating.id,
          reason: modReason.trim(),
        });
        onTriggerToast?.(`Review #${modRating.id} is now hidden.`);
      } else {
        await unhideMutation.mutateAsync({
          id: modRating.id,
          reason: modReason.trim() || 'Restored by platform admin',
        });
        onTriggerToast?.(`Review #${modRating.id} is now visible.`);
      }
      setModRating(null);
      setModAction(null);
      setModReason('');
    } catch {
      onTriggerToast?.('Failed to update rating visibility.');
    }
  };

  const hiddenCount = ratings.filter((r) => r.is_hidden).length;

  return (
    <div className="space-y-6 pb-8 animate-in fade-in duration-150">
      <PageHeader
        title="Ratings & Reviews Moderation"
        subtitle="Ensure fair, verified feedback between NGO relief partners and surplus food donors"
      />

      {/* Moderation Metrics Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-[var(--muted)] font-medium">Total Reviews Filtered</p>
            <p className="text-xl font-bold text-[var(--text)] mt-1">{ratings.length}</p>
          </div>
          <div className="w-10 h-10 rounded-full bg-[var(--primary)]/10 text-[var(--primary)] flex items-center justify-center">
            <MessageSquare className="w-5 h-5" />
          </div>
        </div>

        <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-[var(--muted)] font-medium">Hidden From Public View</p>
            <p className="text-xl font-bold text-amber-500 mt-1">{hiddenCount}</p>
          </div>
          <div className="w-10 h-10 rounded-full bg-amber-500/10 text-amber-500 flex items-center justify-center">
            <EyeOff className="w-5 h-5" />
          </div>
        </div>

        <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-[var(--muted)] font-medium">Active Policy</p>
            <p className="text-xs font-semibold text-emerald-500 mt-1 flex items-center gap-1">
              <CheckCircle2 className="w-4 h-4" /> Dual-Party Audited
            </p>
          </div>
          <div className="w-10 h-10 rounded-full bg-emerald-500/10 text-emerald-500 flex items-center justify-center">
            <ShieldAlert className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-[var(--surface)] p-3 rounded-[12px] border border-[var(--border)]">
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
          <input
            type="text"
            placeholder="Search reviews, businesses, NGOs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full text-xs pl-9 pr-3 py-1.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
          {/* Star Filter */}
          <select
            value={starFilter}
            onChange={(e) => setStarFilter(e.target.value)}
            className="text-xs px-2.5 py-1.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
          >
            <option value="ALL">All Stars</option>
            <option value="5">5 Stars</option>
            <option value="4">4 Stars</option>
            <option value="3">3 Stars</option>
            <option value="2">2 Stars</option>
            <option value="1">1 Star</option>
          </select>

          {/* Visibility Filter */}
          <select
            value={hiddenFilter}
            onChange={(e) => setHiddenFilter(e.target.value)}
            className="text-xs px-2.5 py-1.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
          >
            <option value="ALL">All Visibility</option>
            <option value="VISIBLE">Visible Only</option>
            <option value="HIDDEN">Hidden Only</option>
          </select>
        </div>
      </div>

      {/* Ratings List */}
      {isLoading ? (
        <div className="space-y-3">
          <Skeleton variant="card" className="h-24" />
          <Skeleton variant="card" className="h-24" />
          <Skeleton variant="card" className="h-24" />
        </div>
      ) : ratings.length === 0 ? (
        <div className="bg-[var(--surface)] rounded-[12px] border border-[var(--border)] p-12">
          <EmptyState
            icon={Star}
            title="No reviews found"
            description="No ratings match your filter criteria."
          />
        </div>
      ) : (
        <div className="space-y-4">
          {ratings.map((rating) => (
            <div
              key={rating.id}
              className={`p-5 rounded-[12px] border transition-all ${
                rating.is_hidden
                  ? 'bg-amber-500/5 border-amber-500/30'
                  : 'bg-[var(--surface)] border-[var(--border)] shadow-xs'
              }`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <RatingStars rating={rating.stars} size="sm" />
                  <span className="text-xs font-bold text-[var(--text)]">
                    {rating.stars} / 5 Stars
                  </span>
                  {rating.is_hidden && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-500">
                      <EyeOff className="w-3 h-3" /> HIDDEN FROM PUBLIC
                    </span>
                  )}
                </div>

                <div className="text-xs text-[var(--muted)]">
                  {new Date(rating.created_at).toLocaleDateString()}
                </div>
              </div>

              {/* Reviewer and Donor Info */}
              <div className="flex flex-wrap items-center gap-3 my-3 text-xs">
                <div className="flex items-center gap-1.5 text-[var(--text)] font-semibold">
                  <Users className="w-3.5 h-3.5 text-emerald-500" />
                  <span>{rating.ngo_name}</span>
                </div>
                <span className="text-[var(--muted)]">reviewed donor</span>
                <div className="flex items-center gap-1.5 text-[var(--text)] font-semibold">
                  <Building2 className="w-3.5 h-3.5 text-blue-500" />
                  <span>{rating.business_name}</span>
                </div>
              </div>

              {/* Comment */}
              <div className="p-3 rounded-[8px] bg-[var(--surface-2)] text-xs text-[var(--text)] leading-relaxed italic">
                "{rating.comment || 'No textual feedback provided.'}"
              </div>

              {/* Hidden reason if applicable */}
              {rating.is_hidden && rating.hidden_reason && (
                <div className="mt-2 text-xs text-amber-600 dark:text-amber-400 bg-amber-500/10 p-2.5 rounded-[6px] flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold">Moderation Reason:</span> {rating.hidden_reason}
                  </div>
                </div>
              )}

              {/* Action row */}
              <div className="flex items-center justify-between mt-3 pt-3 border-t border-[var(--border)]">
                <span className="text-[11px] text-[var(--muted)] font-mono">
                  Rating ID #{rating.id} {rating.claim ? `• Claim #${rating.claim}` : ''}
                </span>

                {rating.is_hidden ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setModRating(rating);
                      setModAction('UNHIDE');
                      setModReason('');
                    }}
                    className="text-xs h-7 px-3 text-emerald-500 hover:bg-emerald-500/10 border-emerald-500/30"
                  >
                    <Eye className="w-3.5 h-3.5 mr-1" /> Unhide Review
                  </Button>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setModRating(rating);
                      setModAction('HIDE');
                      setModReason('');
                    }}
                    className="text-xs h-7 px-3 text-amber-500 hover:bg-amber-500/10 border-amber-500/30"
                  >
                    <EyeOff className="w-3.5 h-3.5 mr-1" /> Hide Review
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Moderation Dialog */}
      {modRating && modAction && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150"
        >
          <div className="w-full max-w-md rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center ${
                  modAction === 'HIDE'
                    ? 'bg-amber-500/10 text-amber-500'
                    : 'bg-emerald-500/10 text-emerald-500'
                }`}
              >
                {modAction === 'HIDE' ? (
                  <EyeOff className="w-5 h-5" />
                ) : (
                  <Eye className="w-5 h-5" />
                )}
              </div>
              <div>
                <h3 className="text-sm font-bold text-[var(--text)]">
                  {modAction === 'HIDE' ? 'Hide Rating from Public' : 'Restore Rating Visibility'}
                </h3>
                <p className="text-xs text-[var(--muted)]">Rating ID #{modRating.id}</p>
              </div>
            </div>

            <p className="text-xs text-[var(--text)]">
              {modAction === 'HIDE'
                ? 'Hiding this review will remove its score from the business average rating calculations and hide the comment from the public profile.'
                : 'Unhiding this review will restore its contribution to the business rating summary.'}
            </p>

            <div>
              <label className="text-xs font-semibold text-[var(--text)] block mb-1">
                {modAction === 'HIDE' ? 'Mandatory Moderation Reason' : 'Audit Note (Optional)'}
              </label>
              <textarea
                value={modReason}
                onChange={(e) => setModReason(e.target.value)}
                placeholder={
                  modAction === 'HIDE'
                    ? 'e.g., Inappropriate language, commercial dispute, or unverified claims.'
                    : 'Enter note regarding restoration...'
                }
                rows={3}
                className="w-full text-xs rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setModRating(null);
                  setModAction(null);
                  setModReason('');
                }}
              >
                Cancel
              </Button>
              <Button
                variant={modAction === 'HIDE' ? 'danger' : 'primary'}
                size="sm"
                disabled={modAction === 'HIDE' && !modReason.trim()}
                onClick={handleModeration}
              >
                {modAction === 'HIDE' ? 'Hide Review' : 'Restore Review'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

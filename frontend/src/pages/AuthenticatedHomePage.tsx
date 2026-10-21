import React, { useState, useEffect } from 'react';
import {
  CheckCircle2,
  Clock,
  AlertCircle,
  Truck,
  Package,
  PackagePlus,
  QrCode,
  FileSpreadsheet,
  FileText,
  Sparkles,
  RefreshCw,
  UtensilsCrossed,
  ClipboardList,
  ClipboardPlus,
  Inbox,
  ArrowRight,
  CalendarDays,
  Gift,
  ShieldAlert,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { useHomeData } from '../hooks/useData';
import { StatusBadge } from '../components/ui/StatusBadge';
import { ExpiryPill } from '../components/ui/ExpiryPill';
import { Button } from '../components/ui/Button';
import { simulationEngine } from '../simulation/simulationEngine';
import type {
  BusinessHomeQuickStats,
  NgoHomeQuickStats,
  HomeNeedsAttentionItem,
} from '../types';

export interface AuthenticatedHomePageProps {
  onNavigate: (path: string) => void;
  onOpenAddBatch?: () => void;
  onOpenCreateListing?: () => void;
  onTriggerToast?: (msg: string) => void;
}

/**
 * Returns greeting by local time of day: morning, afternoon, or evening.
 */
function getGreetingTimeOfDay(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

/**
 * Custom count-up animation hook for numeric impact metrics.
 * Respects OS/browser `prefers-reduced-motion` settings and test environments.
 */
function useCountUp(target: number, durationMs: number = 800): number {
  const [value, setValue] = useState(target);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const prefersReducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;
    if (prefersReducedMotion || target === 0 || import.meta.env?.MODE === 'test') {
      const frameId = requestAnimationFrame(() => {
        setValue(target);
      });
      return () => cancelAnimationFrame(frameId);
    }

    let startTime: number | null = null;
    let animationFrameId: number;

    const step = (timestamp: number) => {
      if (!startTime) startTime = timestamp;
      const progress = Math.min((timestamp - startTime) / durationMs, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(eased * target));

      if (progress < 1) {
        animationFrameId = requestAnimationFrame(step);
      }
    };

    animationFrameId = requestAnimationFrame(step);
    return () => cancelAnimationFrame(animationFrameId);
  }, [target, durationMs]);

  return value;
}

export const AuthenticatedHomePage: React.FC<AuthenticatedHomePageProps> = ({
  onNavigate,
  onOpenAddBatch,
  onOpenCreateListing,
}) => {
  const { data, isLoading, isError, error, refetch } = useHomeData();

  // React to simulation engine updates in demo mode
  useEffect(() => {
    const isDemo = typeof window !== 'undefined'
      ? (localStorage.getItem('surplussync_data_mode') ?? 'demo') === 'demo'
      : true;
    if (!isDemo) return;

    const unsubscribe = simulationEngine.subscribe((event) => {
      if (
        event.type === 'NEW_LISTING' ||
        event.type === 'CLAIM_STATUS_CHANGE' ||
        event.type === 'BATCH_ADDED' ||
        event.type === 'POS_SALE' ||
        event.type === 'RESET'
      ) {
        refetch();
      }
    });

    return () => unsubscribe();
  }, [refetch]);

  // Compute impact numbers at top level for consistent hook call order
  const rawKg = data?.impact_snapshot?.kg_redistributed ?? (data?.impact_snapshot as unknown as { kg?: number })?.kg ?? 0;
  const kgAmount = typeof rawKg === 'number' ? rawKg : parseFloat(String(rawKg)) || 0;
  // Exact user brief formula: meals = kg / 0.42, CO2e = kg * 2.5
  const mealsCount = Math.round(kgAmount / 0.42);
  const co2eAmount = Number((kgAmount * 2.5).toFixed(1));

  // Animated counters respecting prefers-reduced-motion (called unconditionally)
  const animatedKg = useCountUp(kgAmount);
  const animatedMeals = useCountUp(mealsCount);
  const animatedCo2e = useCountUp(co2eAmount);

  // Today's formatted date string
  const todayDateStr = new Intl.DateTimeFormat('en-US', {
    weekday: 'long',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date());

  if (isLoading) {
    return (
      <div className="space-y-8 pb-16 animate-in fade-in duration-200" role="status" aria-label="Loading home dashboard">
        {/* Greeting Strip Skeleton */}
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 animate-pulse space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="space-y-2">
              <div className="h-7 w-72 rounded-lg bg-[var(--surface-2)]" />
              <div className="h-4 w-44 rounded-md bg-[var(--surface-2)]" />
            </div>
            <div className="h-10 w-36 rounded-lg bg-[var(--surface-2)]" />
          </div>
        </div>

        {/* Tagline Skeleton */}
        <div className="space-y-2">
          <div className="h-6 w-80 rounded-md bg-[var(--surface-2)] animate-pulse" />
          <div className="h-4 w-96 rounded-md bg-[var(--surface-2)] animate-pulse" />
        </div>

        {/* Bento Grid Skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
          <div className="col-span-12 md:col-span-6 h-64 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 animate-pulse space-y-3">
            <div className="h-5 w-40 rounded-md bg-[var(--surface-2)]" />
            <div className="h-16 rounded-xl bg-[var(--surface-2)]" />
            <div className="h-16 rounded-xl bg-[var(--surface-2)]" />
          </div>
          <div className="col-span-12 md:col-span-3 h-64 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 animate-pulse space-y-3">
            <div className="h-5 w-32 rounded-md bg-[var(--surface-2)]" />
            <div className="h-12 w-20 rounded-lg bg-[var(--surface-2)]" />
            <div className="h-20 rounded-xl bg-[var(--surface-2)]" />
          </div>
          <div className="col-span-12 md:col-span-3 h-64 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 animate-pulse space-y-3">
            <div className="h-5 w-32 rounded-md bg-[var(--surface-2)]" />
            <div className="h-12 w-20 rounded-lg bg-[var(--surface-2)]" />
            <div className="h-20 rounded-xl bg-[var(--surface-2)]" />
          </div>
          <div className="col-span-12 md:col-span-8 h-48 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 animate-pulse" />
          <div className="col-span-12 md:col-span-4 h-48 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 animate-pulse" />
        </div>

        {/* Quick Actions Skeleton */}
        <div className="space-y-3">
          <div className="h-5 w-36 rounded-md bg-[var(--surface-2)] animate-pulse" />
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-20 rounded-xl border border-[var(--border)] bg-[var(--surface)] animate-pulse" />
            ))}
          </div>
        </div>

        {/* Checklist & Activity Skeleton */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="h-60 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 animate-pulse" />
          <div className="h-60 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 animate-pulse" />
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="py-12 flex justify-center">
        <div className="max-w-md w-full p-6 rounded-2xl bg-[var(--surface)] border border-[var(--color-danger)]/30 text-center space-y-4 shadow-sm">
          <div className="w-12 h-12 rounded-full bg-[var(--color-danger-bg)] text-[var(--color-danger)] flex items-center justify-center mx-auto">
            <AlertCircle className="w-6 h-6" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-[var(--text)]">Dashboard Data Unavailable</h2>
            <p className="text-xs text-[var(--muted)] mt-1">
              {error instanceof Error ? error.message : 'Unable to connect to the SurplusSync server.'}
            </p>
          </div>
          <Button variant="primary" onClick={() => refetch()} className="mx-auto flex items-center gap-2">
            <RefreshCw className="w-4 h-4" aria-hidden="true" />
            <span>Retry Connection</span>
          </Button>
        </div>
      </div>
    );
  }

  const {
    greeting,
    quick_stats,
    needs_attention = [],
    getting_started = [],
    recent_activity = [],
    expiring_batches = [],
    new_near_you = [],
    pickups_today = [],
    journey_counts,
  } = data;

  const isBusiness = greeting.role === 'BUSINESS';
  const isNgo = greeting.role === 'NGO';
  const isVerified = Boolean(greeting.is_verified);

  const businessStats = isBusiness ? (quick_stats as BusinessHomeQuickStats) : null;
  const ngoStats = isNgo ? (quick_stats as NgoHomeQuickStats) : null;

  // Getting Started progress calculation
  const totalChecklist = getting_started.length;
  const completedChecklist = getting_started.filter((item) => item.done).length;
  const checklistPercentage = totalChecklist > 0 ? Math.round((completedChecklist / totalChecklist) * 100) : 100;
  const isChecklistDone = totalChecklist > 0 && completedChecklist === totalChecklist;

  const handleActionClick = (link: string) => {
    const cleanLink = link.replace(/^\//, '').trim();
    if (cleanLink === 'add-batch' && onOpenAddBatch) {
      onOpenAddBatch();
    } else {
      onNavigate(cleanLink);
    }
  };

  const getUrgencyBadge = (urgency: HomeNeedsAttentionItem['urgency']) => {
    switch (urgency) {
      case 'critical':
      case 'high':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-[var(--color-danger-bg)] text-[var(--color-danger)] border border-[var(--color-danger)]/30">
            Urgent
          </span>
        );
      case 'medium':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-[var(--color-warning-bg)] text-[var(--color-warning)] border border-[var(--color-warning)]/30">
            Attention
          </span>
        );
      case 'low':
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-[var(--surface-2)] text-[var(--muted)] border border-[var(--border)]">
            Notice
          </span>
        );
    }
  };

  // Surplus Journey Flow stages definition
  const businessStages = [
    {
      id: 'track',
      label: 'Track',
      sublabel: 'Active batches',
      count: journey_counts?.track_or_need ?? 18,
      link: 'inventory',
      icon: Package,
      ariaLabel: `Track, ${journey_counts?.track_or_need ?? 18} active batches in inventory`,
    },
    {
      id: 'spot',
      label: 'Spot',
      sublabel: 'Expiring in 48h',
      count: journey_counts?.spot_or_match ?? businessStats?.batches_expiring_48h ?? 0,
      link: 'inventory',
      icon: Clock,
      ariaLabel: `Spot, ${journey_counts?.spot_or_match ?? businessStats?.batches_expiring_48h ?? 0} batches expiring within 48 hours`,
    },
    {
      id: 'share',
      label: 'Share',
      sublabel: 'Open listings',
      count: journey_counts?.share_or_request ?? businessStats?.active_listings ?? 0,
      link: 'marketplace',
      icon: Gift,
      ariaLabel: `Share, ${journey_counts?.share_or_request ?? businessStats?.active_listings ?? 0} open surplus listings`,
    },
    {
      id: 'collect',
      label: 'Collect',
      sublabel: 'Pickups scheduled',
      count: journey_counts?.collect ?? businessStats?.pickups_scheduled_24h ?? 0,
      link: 'schedule',
      icon: Truck,
      ariaLabel: `Collect, ${journey_counts?.collect ?? businessStats?.pickups_scheduled_24h ?? 0} scheduled pickups`,
    },
    {
      id: 'done',
      label: 'Done',
      sublabel: 'Completed donations',
      count: journey_counts?.done_or_received ?? (rawKg > 0 ? 6 : 0),
      link: 'impact',
      icon: CheckCircle2,
      ariaLabel: `Done, ${journey_counts?.done_or_received ?? (rawKg > 0 ? 6 : 0)} completed donations this month`,
    },
  ];

  const ngoStages = [
    {
      id: 'need',
      label: 'Need',
      sublabel: 'Active requirements',
      count: journey_counts?.track_or_need ?? ngoStats?.active_requirements ?? 0,
      link: 'requirements',
      icon: ClipboardList,
      ariaLabel: `Need, ${journey_counts?.track_or_need ?? ngoStats?.active_requirements ?? 0} active food requirements`,
    },
    {
      id: 'match',
      label: 'Match',
      sublabel: 'New matching listings',
      count: journey_counts?.spot_or_match ?? ngoStats?.new_matching_listings_24h ?? 0,
      link: 'feed',
      icon: Sparkles,
      ariaLabel: `Match, ${journey_counts?.spot_or_match ?? ngoStats?.new_matching_listings_24h ?? 0} new matching listings nearby`,
    },
    {
      id: 'request',
      label: 'Request',
      sublabel: 'Open requests',
      count: journey_counts?.share_or_request ?? ngoStats?.open_requests_awaiting_donor ?? 0,
      link: 'donations',
      icon: FileText,
      ariaLabel: `Request, ${journey_counts?.share_or_request ?? ngoStats?.open_requests_awaiting_donor ?? 0} open rescue requests`,
    },
    {
      id: 'collect',
      label: 'Collect',
      sublabel: 'Pickups scheduled',
      count: journey_counts?.collect ?? ngoStats?.pickups_scheduled_24h ?? 0,
      link: 'schedule',
      icon: Truck,
      ariaLabel: `Collect, ${journey_counts?.collect ?? ngoStats?.pickups_scheduled_24h ?? 0} scheduled pickups`,
    },
    {
      id: 'received',
      label: 'Received',
      sublabel: 'Completed this month',
      count: journey_counts?.done_or_received ?? (rawKg > 0 ? 4 : 0),
      link: 'donations',
      icon: CheckCircle2,
      ariaLabel: `Received, ${journey_counts?.done_or_received ?? (rawKg > 0 ? 4 : 0)} food donations received this month`,
    },
  ];

  const currentStages = isBusiness ? businessStages : ngoStages;

  // The path line fills according to where the user's work currently is (the stage with the most pending items)
  let highlightedStageIndex = 0;
  let maxStageCount = -1;
  currentStages.forEach((stage, idx) => {
    if (stage.count > maxStageCount && stage.count > 0) {
      maxStageCount = stage.count;
      highlightedStageIndex = idx;
    }
  });

  return (
    <div className="space-y-8 pb-16 animate-in fade-in duration-300">
      {/* 1. GREETING STRIP (full width, compact, subtle dotted pattern) */}
      <section
        aria-label="Welcome greeting"
        className={cn(
          'relative overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 shadow-sm transition-all',
          'before:absolute before:inset-0 before:pointer-events-none before:opacity-[0.03] dark:before:opacity-[0.05]',
          'before:bg-[radial-gradient(#000000_1px,transparent_1px)] dark:before:bg-[radial-gradient(#ffffff_1px,transparent_1px)] before:[background-size:16px_16px]'
        )}
      >
        <div className="relative z-10 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--text)]">
                {getGreetingTimeOfDay()}, {greeting.organization_name}
              </h1>
              {isVerified ? (
                <StatusBadge variant="success" size="sm" dot>
                  Verified
                </StatusBadge>
              ) : (
                <StatusBadge variant="warning" size="sm" dot>
                  Pending verification
                </StatusBadge>
              )}
            </div>
            <p className="text-xs text-[var(--muted)] flex items-center gap-2">
              <CalendarDays className="w-3.5 h-3.5" aria-hidden="true" />
              <span>{todayDateStr}</span>
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            {isBusiness ? (
              <Button
                variant="primary"
                onClick={() => (onOpenCreateListing ? onOpenCreateListing() : handleActionClick('marketplace'))}
                className="gap-2 shadow-sm font-semibold text-sm"
                aria-label="Offer surplus food"
              >
                <Gift className="w-4 h-4" aria-hidden="true" />
                <span>Offer surplus</span>
              </Button>
            ) : (
              <Button
                variant="primary"
                onClick={() => handleActionClick('feed')}
                disabled={!isVerified}
                className="gap-2 shadow-sm font-semibold text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label={isVerified ? 'Browse the feed' : 'Browse the feed (requires verified account)'}
                title={!isVerified ? 'Your organization must be verified by an administrator to claim donations.' : undefined}
              >
                <UtensilsCrossed className="w-4 h-4" aria-hidden="true" />
                <span>Browse the feed</span>
              </Button>
            )}
          </div>
        </div>
      </section>

      {/* 2. TAGLINE ROW (small, calm, not a hero, 2 lines total) */}
      <section aria-label="Platform mission" className="px-1 space-y-1">
        <h2 className="text-base sm:text-lg font-semibold text-[var(--text)] tracking-tight">
          {isBusiness ? "Know what's expiring. Share what's left." : "See what's available. Feed who's waiting."}
        </h2>
        <p className="text-xs sm:text-sm text-[var(--muted)] leading-relaxed">
          {isBusiness
            ? 'Track inventory in real time, prevent waste, and redirect surplus food to local community partners.'
            : 'Discover available donations nearby, coordinate seamless pickups, and support your community.'}
        </p>
      </section>

      {/* UNVERIFIED / PENDING NGO CALM BANNER */}
      {isNgo && !isVerified && (
        <aside
          aria-label="Verification pending notice"
          className="rounded-xl border border-amber-500/30 bg-amber-500/10 dark:bg-amber-500/5 p-4 text-xs flex items-start gap-3"
        >
          <ShieldAlert className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" aria-hidden="true" />
          <div className="space-y-0.5">
            <p className="font-semibold text-amber-900 dark:text-amber-200">
              Account pending administrator verification
            </p>
            <p className="text-amber-800/90 dark:text-amber-300/80 leading-relaxed">
              An administrator must verify your organization before you can request food donations. All other platform features, profile management, and requirement settings remain fully usable.
            </p>
          </div>
        </aside>
      )}

      {/* 3. TODAY BENTO GRID (12-column grid, the main focus of the page) */}
      <section aria-label="Today's overview" className="space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold tracking-wide uppercase text-[var(--muted)]">
            Today
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-stretch">
          {/* TILE 1 (6 COLUMNS): Needs Attention */}
          <div className="col-span-12 md:col-span-6 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 flex flex-col justify-between shadow-sm">
            <div>
              <div className="flex items-center justify-between pb-3 border-b border-[var(--border)] mb-4">
                <div className="flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-amber-500" aria-hidden="true" />
                  <h3 className="text-sm font-bold text-[var(--text)]">Needs attention</h3>
                </div>
                {needs_attention.length > 0 && (
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-[var(--surface-2)] text-[var(--text)] border border-[var(--border)]">
                    {needs_attention.length}
                  </span>
                )}
              </div>

              {needs_attention.length === 0 ? (
                <div className="py-6 flex flex-col items-center justify-center text-center space-y-2">
                  <div className="w-10 h-10 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
                    <CheckCircle2 className="w-5 h-5" aria-hidden="true" />
                  </div>
                  <p className="text-sm font-semibold text-[var(--text)]">You're all caught up</p>
                  <p className="text-xs text-[var(--muted)] max-w-xs">
                    No urgent actions require your attention right now.
                  </p>
                </div>
              ) : (
                <div className="space-y-2.5">
                  {needs_attention.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => handleActionClick(item.link)}
                      className="w-full text-left p-3 rounded-xl border border-[var(--border)] bg-[var(--surface-2)]/50 hover:bg-[var(--surface-2)] transition-colors flex items-center justify-between gap-3 group focus:outline-none focus:ring-2 focus:ring-violet-500"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        {getUrgencyBadge(item.urgency)}
                        <span className="text-xs font-medium text-[var(--text)] truncate">
                          {item.title}
                        </span>
                      </div>
                      <ArrowRight className="w-3.5 h-3.5 text-[var(--muted)] group-hover:text-[var(--text)] shrink-0 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="pt-4 mt-auto">
              <button
                onClick={() => handleActionClick(isBusiness ? 'alerts' : 'feed')}
                className="text-xs font-medium text-violet-600 dark:text-violet-400 hover:underline flex items-center gap-1 focus:outline-none focus:ring-1 focus:ring-violet-500 rounded"
              >
                <span>{isBusiness ? 'View all alerts' : 'View recent updates'}</span>
                <ArrowRight className="w-3 h-3" aria-hidden="true" />
              </button>
            </div>
          </div>

          {/* TILE 2 (3 COLUMNS): Expiring Soon (Business) OR New Near You (NGO) */}
          <div className="col-span-12 md:col-span-3 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 flex flex-col justify-between shadow-sm">
            <div>
              <div className="flex items-center justify-between pb-3 border-b border-[var(--border)] mb-3">
                <div className="flex items-center gap-2">
                  {isBusiness ? (
                    <Clock className="w-4 h-4 text-violet-500" aria-hidden="true" />
                  ) : (
                    <Sparkles className="w-4 h-4 text-violet-500" aria-hidden="true" />
                  )}
                  <h3 className="text-sm font-bold text-[var(--text)]">
                    {isBusiness ? 'Expiring soon' : 'New near you'}
                  </h3>
                </div>
                <span className="text-xs font-bold text-[var(--text)]">
                  {isBusiness
                    ? (businessStats?.batches_expiring_48h ?? expiring_batches.length)
                    : (ngoStats?.new_matching_listings_24h ?? new_near_you.length)}
                </span>
              </div>

              {isBusiness ? (
                expiring_batches.length > 0 ? (
                  <div className="space-y-2">
                    {expiring_batches.slice(0, 3).map((b) => (
                      <div
                        key={b.id}
                        onClick={() => handleActionClick('inventory')}
                        className="p-2 rounded-lg bg-[var(--surface-2)]/40 border border-[var(--border)] flex items-center justify-between gap-2 cursor-pointer hover:bg-[var(--surface-2)] transition-colors"
                      >
                        <div className="min-w-0">
                          <p className="text-xs font-medium text-[var(--text)] truncate">{b.product_name}</p>
                          <p className="text-[11px] text-[var(--muted)]">{b.quantity} {b.unit || 'kg'}</p>
                        </div>
                        <ExpiryPill
                          expiryDate={b.expiry_date || '2026-10-21T18:00:00Z'}
                          className="shrink-0 text-[10px]"
                        />
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-[var(--muted)] py-4">No batches expiring within 48 hours.</p>
                )
              ) : (
                new_near_you.length > 0 ? (
                  <div className="space-y-2">
                    {new_near_you.slice(0, 3).map((item) => (
                      <div
                        key={item.id}
                        onClick={() => handleActionClick('feed')}
                        className="p-2 rounded-lg bg-[var(--surface-2)]/40 border border-[var(--border)] flex items-center justify-between gap-2 cursor-pointer hover:bg-[var(--surface-2)] transition-colors"
                      >
                        <div className="min-w-0">
                          <p className="text-xs font-medium text-[var(--text)] truncate">{item.title}</p>
                          <p className="text-[11px] text-[var(--muted)]">{item.distance_km} km away</p>
                        </div>
                        <span className="text-[11px] font-semibold text-[var(--text)] shrink-0">
                          {item.quantity} {item.unit || 'kg'}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-[var(--muted)] py-4">No new matching listings nearby right now.</p>
                )
              )}
            </div>

            <div className="pt-3 mt-auto">
              <button
                onClick={() => handleActionClick(isBusiness ? 'inventory' : 'feed')}
                className="text-xs font-medium text-violet-600 dark:text-violet-400 hover:underline flex items-center gap-1 focus:outline-none focus:ring-1 focus:ring-violet-500 rounded"
              >
                <span>{isBusiness ? 'Open inventory' : 'Browse food feed'}</span>
                <ArrowRight className="w-3 h-3" aria-hidden="true" />
              </button>
            </div>
          </div>

          {/* TILE 3 (3 COLUMNS): Pickups Today */}
          <div className="col-span-12 md:col-span-3 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 flex flex-col justify-between shadow-sm">
            <div>
              <div className="flex items-center justify-between pb-3 border-b border-[var(--border)] mb-3">
                <div className="flex items-center gap-2">
                  <Truck className="w-4 h-4 text-emerald-500" aria-hidden="true" />
                  <h3 className="text-sm font-bold text-[var(--text)]">Pickups today</h3>
                </div>
                <span className="text-xs font-bold text-[var(--text)]">
                  {isBusiness ? (businessStats?.pickups_scheduled_24h ?? pickups_today.length) : (ngoStats?.pickups_scheduled_24h ?? pickups_today.length)}
                </span>
              </div>

              {pickups_today.length > 0 ? (
                <div className="space-y-2">
                  {pickups_today.slice(0, 3).map((p) => (
                    <div
                      key={p.id}
                      onClick={() => handleActionClick('schedule')}
                      className="p-2 rounded-lg bg-[var(--surface-2)]/40 border border-[var(--border)] flex items-center justify-between gap-2 cursor-pointer hover:bg-[var(--surface-2)] transition-colors"
                    >
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-[var(--text)] truncate">{p.counterpart_name}</p>
                        <p className="text-[11px] text-[var(--muted)] flex items-center gap-1">
                          <Clock className="w-3 h-3 text-[var(--muted)]" aria-hidden="true" />
                          <span>{p.time}</span>
                        </p>
                      </div>
                      <StatusBadge variant="info" size="sm" className="shrink-0 text-[10px]">
                        {p.status}
                      </StatusBadge>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-[var(--muted)] py-4">No pickups scheduled today.</p>
              )}
            </div>

            <div className="pt-3 mt-auto">
              <button
                onClick={() => handleActionClick('schedule')}
                className="text-xs font-medium text-violet-600 dark:text-violet-400 hover:underline flex items-center gap-1 focus:outline-none focus:ring-1 focus:ring-violet-500 rounded"
              >
                <span>View schedule</span>
                <ArrowRight className="w-3 h-3" aria-hidden="true" />
              </button>
            </div>
          </div>

          {/* TILE 4 (WIDE TILE, 8 COLUMNS): Surplus Journey Flow (Task 2) */}
          <div className="col-span-12 md:col-span-8 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 flex flex-col justify-between shadow-sm relative overflow-hidden dark:shadow-violet-950/20">
            {/* Soft subtle glow behind journey in dark mode */}
            <div
              className="absolute -top-12 -right-12 w-64 h-64 bg-violet-600/5 dark:bg-violet-500/10 rounded-full blur-3xl pointer-events-none -z-0"
              aria-hidden="true"
            />

            <div className="relative z-10">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pb-4 border-b border-[var(--border)] mb-5">
                <div>
                  <h3 className="text-sm font-bold text-[var(--text)]">Surplus journey</h3>
                  <p className="text-xs text-[var(--muted)] mt-0.5">
                    {isBusiness ? 'Track live inventory flow from stock to donation' : 'Track redistribution from requirement to pickup'}
                  </p>
                </div>
                <span className="text-[11px] font-medium text-[var(--muted)] self-start sm:self-auto">
                  Stage highlighted: <strong className="text-violet-600 dark:text-violet-400">{currentStages[highlightedStageIndex]?.label}</strong>
                </span>
              </div>

              {/* Connected Nodes Path (horizontal on desktop, vertical on mobile) */}
              <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 md:gap-2 relative">
                {/* Vertical connecting track on mobile */}
                <div
                  className="md:hidden absolute left-[30px] top-6 bottom-6 w-0.5 bg-[var(--border)] -z-0 pointer-events-none"
                  aria-hidden="true"
                />

                {currentStages.map((stage, idx) => {
                  const Icon = stage.icon;
                  const isHighlighted = idx === highlightedStageIndex;
                  const isFilled = idx <= highlightedStageIndex;
                  const isZero = stage.count === 0;

                  return (
                    <React.Fragment key={stage.id}>
                      <button
                        type="button"
                        onClick={() => handleActionClick(stage.link)}
                        aria-label={stage.ariaLabel}
                        style={{ animationDelay: `${idx * 60}ms`, animationFillMode: 'both' }}
                        className={cn(
                          'flex-1 flex flex-row md:flex-col items-center md:text-center p-3 rounded-xl border transition-all text-left md:text-center group relative z-10',
                          'focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-zinc-900',
                          'motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-1 duration-300',
                          isHighlighted
                            ? 'border-violet-500 bg-violet-500/10 dark:bg-violet-500/15 shadow-sm'
                            : 'border-[var(--border)] bg-[var(--surface-2)]/30 hover:bg-[var(--surface-2)] hover:border-violet-300 dark:hover:border-violet-700/50'
                        )}
                      >
                        <div
                          className={cn(
                            'w-9 h-9 rounded-full flex items-center justify-center shrink-0 mb-0 md:mb-2 mr-3 md:mr-0 transition-colors',
                            isHighlighted
                              ? 'bg-violet-600 text-white shadow-sm ring-4 ring-violet-500/20'
                              : isFilled
                              ? 'bg-violet-100 dark:bg-violet-950/60 text-violet-600 dark:text-violet-400'
                              : 'bg-[var(--surface-2)] text-[var(--muted)]'
                          )}
                        >
                          <Icon className="w-4 h-4" aria-hidden="true" />
                        </div>

                        <div className="min-w-0 flex-1 md:flex-initial">
                          <p className="text-xs font-bold text-[var(--text)] flex items-center md:justify-center gap-1.5">
                            <span>{stage.label}</span>
                            {isHighlighted && (
                              <span className="w-1.5 h-1.5 rounded-full bg-violet-600 dark:bg-violet-400 animate-pulse" aria-hidden="true" />
                            )}
                          </p>
                          <p className="text-[11px] text-[var(--muted)] truncate">
                            {stage.sublabel}
                          </p>
                        </div>

                        <div className="shrink-0 md:mt-2">
                          <span
                            className={cn(
                              'inline-block px-2 py-0.5 text-xs font-bold rounded-full',
                              isZero
                                ? 'text-zinc-400 dark:text-zinc-500 bg-transparent'
                                : isHighlighted
                                ? 'bg-violet-600 text-white'
                                : 'bg-[var(--surface-2)] text-[var(--text)] border border-[var(--border)]'
                            )}
                          >
                            {isZero ? '—' : stage.count}
                          </span>
                        </div>
                      </button>

                      {/* Connecting Line between nodes on desktop */}
                      {idx < currentStages.length - 1 && (
                        <div
                          className={cn(
                            'hidden md:block h-0.5 flex-1 mx-1 rounded-full transition-colors',
                            idx < highlightedStageIndex
                              ? 'bg-violet-500 dark:bg-violet-400'
                              : 'bg-[var(--border)]'
                          )}
                          aria-hidden="true"
                        />
                      )}
                    </React.Fragment>
                  );
                })}
              </div>
            </div>

            <div className="pt-4 mt-auto relative z-10 flex items-center justify-between text-xs text-[var(--muted)]">
              <span>Click any stage node to manage related items</span>
              <button
                onClick={() => handleActionClick(isBusiness ? 'inventory' : 'requirements')}
                className="font-medium text-violet-600 dark:text-violet-400 hover:underline flex items-center gap-1 focus:outline-none focus:ring-1 focus:ring-violet-500 rounded"
              >
                <span>View details</span>
                <ArrowRight className="w-3 h-3" aria-hidden="true" />
              </button>
            </div>
          </div>

          {/* TILE 5 (4 COLUMNS): Your impact, last 30 days */}
          <div className="col-span-12 md:col-span-4 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 flex flex-col justify-between shadow-sm">
            <div>
              <div className="flex items-center justify-between pb-3 border-b border-[var(--border)] mb-4">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-violet-500" aria-hidden="true" />
                  <h3 className="text-sm font-bold text-[var(--text)]">Your impact, last 30 days</h3>
                </div>
              </div>

              {kgAmount === 0 ? (
                <div className="py-6 text-center space-y-2">
                  <p className="text-xs text-[var(--muted)] leading-relaxed">
                    Your impact appears after your first completed donation
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Three key metrics: kg, meals (kg / 0.42), CO2e (kg * 2.5) */}
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="p-2.5 rounded-xl bg-[var(--surface-2)]/50 border border-[var(--border)]">
                      <p className="text-base sm:text-lg font-bold text-[var(--text)]">
                        {animatedKg.toLocaleString()}
                      </p>
                      <p className="text-[10px] text-[var(--muted)] font-medium">kg saved</p>
                    </div>
                    <div className="p-2.5 rounded-xl bg-[var(--surface-2)]/50 border border-[var(--border)]">
                      <p className="text-base sm:text-lg font-bold text-violet-600 dark:text-violet-400">
                        {animatedMeals.toLocaleString()}
                      </p>
                      <p className="text-[10px] text-[var(--muted)] font-medium">meals</p>
                    </div>
                    <div className="p-2.5 rounded-xl bg-[var(--surface-2)]/50 border border-[var(--border)]">
                      <p className="text-base sm:text-lg font-bold text-emerald-600 dark:text-emerald-400">
                        {animatedCo2e.toLocaleString()}
                      </p>
                      <p className="text-[10px] text-[var(--muted)] font-medium">kg CO₂e</p>
                    </div>
                  </div>

                  {/* Tiny trend sparkline */}
                  <div className="pt-2">
                    <p className="text-[10px] text-[var(--muted)] mb-1">30-day rescue velocity</p>
                    <svg viewBox="0 0 100 24" className="w-full h-6 overflow-visible" aria-hidden="true">
                      <polyline
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        className="text-violet-500 dark:text-violet-400"
                        points="0,20 15,18 30,22 45,14 60,16 75,8 90,11 100,3"
                      />
                    </svg>
                  </div>
                </div>
              )}
            </div>

            <div className="pt-4 mt-auto">
              <button
                onClick={() => handleActionClick('impact')}
                className="text-xs font-medium text-violet-600 dark:text-violet-400 hover:underline flex items-center gap-1 focus:outline-none focus:ring-1 focus:ring-violet-500 rounded"
              >
                <span>View full analytics</span>
                <ArrowRight className="w-3 h-3" aria-hidden="true" />
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* 4. QUICK ACTIONS ROW (Icon tiles named by action, not by feature) */}
      <section aria-label="Quick actions" className="space-y-3">
        <h2 className="text-sm font-semibold tracking-wide uppercase text-[var(--muted)]">
          Quick actions
        </h2>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {isBusiness ? (
            <>
              <button
                onClick={() => (onOpenAddBatch ? onOpenAddBatch() : handleActionClick('inventory'))}
                className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-2)] transition-colors flex items-center gap-3 text-left group focus:outline-none focus:ring-2 focus:ring-violet-500"
                aria-label="Add stock to inventory"
              >
                <div className="w-9 h-9 rounded-lg bg-violet-500/10 text-violet-600 dark:text-violet-400 flex items-center justify-center shrink-0">
                  <PackagePlus className="w-4 h-4" aria-hidden="true" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-bold text-[var(--text)] group-hover:text-violet-600 dark:group-hover:text-violet-400 transition-colors">
                    Add stock
                  </p>
                  <p className="text-[11px] text-[var(--muted)] truncate">New inventory batch</p>
                </div>
              </button>

              <button
                onClick={() => handleActionClick('scan')}
                className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-2)] transition-colors flex items-center gap-3 text-left group focus:outline-none focus:ring-2 focus:ring-violet-500"
                aria-label="Scan a code with barcode camera"
              >
                <div className="w-9 h-9 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0">
                  <QrCode className="w-4 h-4" aria-hidden="true" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-bold text-[var(--text)] group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors">
                    Scan a code
                  </p>
                  <p className="text-[11px] text-[var(--muted)] truncate">Lookup barcode or QR</p>
                </div>
              </button>

              <button
                onClick={() => handleActionClick('import')}
                className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-2)] transition-colors flex items-center gap-3 text-left group focus:outline-none focus:ring-2 focus:ring-violet-500"
                aria-label="Import a file with bulk CSV or POS"
              >
                <div className="w-9 h-9 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0">
                  <FileSpreadsheet className="w-4 h-4" aria-hidden="true" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-bold text-[var(--text)] group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                    Import a file
                  </p>
                  <p className="text-[11px] text-[var(--muted)] truncate">Bulk CSV or POS sync</p>
                </div>
              </button>

              <button
                onClick={() => (onOpenCreateListing ? onOpenCreateListing() : handleActionClick('marketplace'))}
                className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-2)] transition-colors flex items-center gap-3 text-left group focus:outline-none focus:ring-2 focus:ring-violet-500"
                aria-label="Offer surplus food on the marketplace"
              >
                <div className="w-9 h-9 rounded-lg bg-coral-500/10 text-[var(--accent)] flex items-center justify-center shrink-0">
                  <Gift className="w-4 h-4" aria-hidden="true" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-bold text-[var(--text)] group-hover:text-[var(--accent)] transition-colors">
                    Offer surplus
                  </p>
                  <p className="text-[11px] text-[var(--muted)] truncate">List for rescue</p>
                </div>
              </button>

              <button
                onClick={() => handleActionClick('donations')}
                className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-2)] transition-colors flex items-center gap-3 text-left group focus:outline-none focus:ring-2 focus:ring-violet-500"
                aria-label="Review donation requests"
              >
                <div className="w-9 h-9 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center shrink-0">
                  <Inbox className="w-4 h-4" aria-hidden="true" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-bold text-[var(--text)] group-hover:text-amber-600 dark:group-hover:text-amber-400 transition-colors">
                    Review requests
                  </p>
                  <p className="text-[11px] text-[var(--muted)] truncate">Partner claims</p>
                </div>
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => handleActionClick('feed')}
                disabled={!isVerified}
                className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-2)] transition-colors flex items-center gap-3 text-left group focus:outline-none focus:ring-2 focus:ring-violet-500 disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Browse the feed for surplus listings"
              >
                <div className="w-9 h-9 rounded-lg bg-violet-500/10 text-violet-600 dark:text-violet-400 flex items-center justify-center shrink-0">
                  <UtensilsCrossed className="w-4 h-4" aria-hidden="true" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-bold text-[var(--text)] group-hover:text-violet-600 dark:group-hover:text-violet-400 transition-colors">
                    Browse the feed
                  </p>
                  <p className="text-[11px] text-[var(--muted)] truncate">Available donations</p>
                </div>
              </button>

              <button
                onClick={() => handleActionClick('requirements')}
                disabled={!isVerified}
                className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-2)] transition-colors flex items-center gap-3 text-left group focus:outline-none focus:ring-2 focus:ring-violet-500 disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Add a food requirement for your kitchen"
              >
                <div className="w-9 h-9 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0">
                  <ClipboardPlus className="w-4 h-4" aria-hidden="true" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-bold text-[var(--text)] group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors">
                    Add a requirement
                  </p>
                  <p className="text-[11px] text-[var(--muted)] truncate">Specify food needs</p>
                </div>
              </button>

              <button
                onClick={() => handleActionClick('donations')}
                disabled={!isVerified}
                className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-2)] transition-colors flex items-center gap-3 text-left group focus:outline-none focus:ring-2 focus:ring-violet-500 disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="My requests"
              >
                <div className="w-9 h-9 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0">
                  <FileText className="w-4 h-4" aria-hidden="true" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-bold text-[var(--text)] group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                    My requests
                  </p>
                  <p className="text-[11px] text-[var(--muted)] truncate">Status & claims</p>
                </div>
              </button>

              <button
                onClick={() => handleActionClick('schedule')}
                className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-2)] transition-colors flex items-center gap-3 text-left group focus:outline-none focus:ring-2 focus:ring-violet-500"
                aria-label="Pickup schedule"
              >
                <div className="w-9 h-9 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center shrink-0">
                  <CalendarDays className="w-4 h-4" aria-hidden="true" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-bold text-[var(--text)] group-hover:text-amber-600 dark:group-hover:text-amber-400 transition-colors">
                    Pickup schedule
                  </p>
                  <p className="text-[11px] text-[var(--muted)] truncate">Timeline & routes</p>
                </div>
              </button>
            </>
          )}
        </div>
      </section>

      {/* 5. SETUP CHECKLIST & RECENT ACTIVITY (Side by side; checklist disappears when complete) */}
      <section
        aria-label="Account progress and recent activity"
        className={cn(
          'grid gap-6',
          isChecklistDone ? 'grid-cols-1' : 'grid-cols-1 lg:grid-cols-2'
        )}
      >
        {/* Setup Checklist Card (Disappears completely when isChecklistDone is true) */}
        {!isChecklistDone && getting_started.length > 0 && (
          <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 space-y-4 shadow-sm">
            <div className="flex items-center justify-between pb-3 border-b border-[var(--border)]">
              <div>
                <h3 className="text-sm font-bold text-[var(--text)]">Getting started checklist</h3>
                <p className="text-xs text-[var(--muted)] mt-0.5">
                  Complete account setup tasks to unlock full redistribution workflows
                </p>
              </div>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-600 dark:text-violet-400 border border-violet-500/20">
                {checklistPercentage}% done
              </span>
            </div>

            {/* Progress Bar */}
            <div
              className="w-full bg-[var(--surface-2)] rounded-full h-2 overflow-hidden"
              role="progressbar"
              aria-valuenow={checklistPercentage}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Setup checklist progress"
            >
              <div
                className="bg-violet-600 h-2 rounded-full transition-all duration-500"
                style={{ width: `${checklistPercentage}%` }}
              />
            </div>

            <div className="space-y-2 pt-1">
              {getting_started.map((item) => (
                <button
                  key={item.id}
                  onClick={() => handleActionClick(item.link)}
                  className={cn(
                    'w-full text-left p-3 rounded-xl border transition-colors flex items-center justify-between gap-3 group focus:outline-none focus:ring-2 focus:ring-violet-500',
                    item.done
                      ? 'border-[var(--border)]/60 bg-[var(--surface-2)]/20 opacity-75'
                      : 'border-[var(--border)] bg-[var(--surface-2)]/50 hover:bg-[var(--surface-2)]'
                  )}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <CheckCircle2
                      className={cn(
                        'w-4 h-4 shrink-0 transition-colors',
                        item.done ? 'text-emerald-500' : 'text-[var(--muted)]'
                      )}
                      aria-hidden="true"
                    />
                    <span
                      className={cn(
                        'text-xs font-medium text-[var(--text)] truncate',
                        item.done && 'line-through text-[var(--muted)]'
                      )}
                    >
                      {item.title}
                    </span>
                  </div>
                  <ArrowRight className="w-3.5 h-3.5 text-[var(--muted)] group-hover:text-[var(--text)] shrink-0 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Recent Activity Card */}
        <div
          className={cn(
            'rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 space-y-4 shadow-sm',
            isChecklistDone && 'w-full'
          )}
        >
          <div className="flex items-center justify-between pb-3 border-b border-[var(--border)]">
            <div>
              <h3 className="text-sm font-bold text-[var(--text)]">Recent activity</h3>
              <p className="text-xs text-[var(--muted)] mt-0.5">
                Real-time activity log across your organization
              </p>
            </div>
          </div>

          {recent_activity.length === 0 ? (
            <div className="py-8 text-center space-y-1">
              <p className="text-xs font-semibold text-[var(--text)]">No recent events</p>
              <p className="text-xs text-[var(--muted)]">Activity will appear as actions occur.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {recent_activity.slice(0, 5).map((act) => (
                <div
                  key={act.id}
                  onClick={() => handleActionClick(act.link)}
                  className="p-3 rounded-xl border border-[var(--border)] bg-[var(--surface-2)]/40 hover:bg-[var(--surface-2)] transition-colors flex items-center justify-between gap-3 cursor-pointer group"
                >
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-[var(--text)] truncate">{act.title}</p>
                    <p className="text-[11px] text-[var(--muted)] flex items-center gap-1 mt-0.5">
                      <Clock className="w-3 h-3 text-[var(--muted)]" aria-hidden="true" />
                      <span>{act.time}</span>
                    </p>
                  </div>
                  <ArrowRight className="w-3.5 h-3.5 text-[var(--muted)] group-hover:text-[var(--text)] shrink-0 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
};

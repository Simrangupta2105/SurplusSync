import React, { useMemo } from 'react';
import {
  Package,
  Clock,
  AlertTriangle,
  HeartHandshake,
  Sparkles,
  ArrowRight,
  TrendingDown,
  Layers,
  CheckCircle2,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { StatCard } from '../../components/ui/StatCard';
import { ExpiryPill } from '../../components/ui/ExpiryPill';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { Button } from '../../components/ui/Button';
import { PageHeader } from '../../components/ui/PageHeader';
import {
  useDashboardSummary,
  useExpiringBatches,
  useAlerts,
  useAcknowledgeAlert,
  useCurrentUser,
} from '../../hooks/useData';
import { BusinessRatingCard } from '../../components/business/BusinessRatingCard';
import { SalesForecastCard } from '../../components/business/SalesForecastCard';
import type { BatchWithProduct, Alert } from '../../types';

interface BusinessDashboardPageProps {
  onNavigate: (path: string) => void;
  onOpenAddBatch: () => void;
  onOpenCreateListing: (batchId: number) => void;
  onTriggerToast: (msg: string) => void;
}

// 30-day trend data showing diverted/donated surplus vs avoided waste
const trendData = [
  { day: 'Day 1', donated: 110, wasted: 42 },
  { day: 'Day 5', donated: 175, wasted: 34 },
  { day: 'Day 10', donated: 260, wasted: 28 },
  { day: 'Day 15', donated: 340, wasted: 19 },
  { day: 'Day 20', donated: 430, wasted: 14 },
  { day: 'Day 25', donated: 520, wasted: 9 },
  { day: 'Day 30', donated: 645, wasted: 5 },
];

export const BusinessDashboardPage: React.FC<BusinessDashboardPageProps> = ({
  onNavigate,
  onOpenAddBatch,
  onOpenCreateListing,
  onTriggerToast,
}) => {
  const { data: user } = useCurrentUser();
  const { data: summary, isLoading: isSummaryLoading } = useDashboardSummary();
  const { data: expiringBatches, isLoading: isExpiringLoading } = useExpiringBatches(5);
  const { data: alerts, isLoading: isAlertsLoading } = useAlerts();
  const ackMutation = useAcknowledgeAlert();

  const handleAcknowledge = (id: number) => {
    ackMutation.mutate(id, {
      onSuccess: () => onTriggerToast('Alert marked as acknowledged'),
    });
  };

  const topExpiring = (expiringBatches || []).slice(0, 5);
  const todayStr = new Date().toISOString().split('T')[0];
  const validAlerts = useMemo(() => {
    return (alerts || []).filter((a: Alert) => {
      if (a.batch_status === 'EXPIRED') return false;
      if (a.expiry_date && a.expiry_date < todayStr) return false;
      if (a.message && /\b(has expired|is expired|expired on)\b/i.test(a.message)) return false;
      return true;
    });
  }, [alerts, todayStr]);
  const activeAlerts = validAlerts.filter((a: Alert) => !a.is_acknowledged).slice(0, 4);

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Page Header */}
      <PageHeader
        title="Inventory & Surplus Overview"
        description="Monitor active shelf-life horizons, stock conservation invariants, and donation dispatches in real time."
        action={
          <div className="flex items-center gap-2.5">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onNavigate('alerts')}
              className="gap-1.5"
            >
              <AlertTriangle className="w-4 h-4 text-[var(--color-warning)]" />
              <span>Review Alerts</span>
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={onOpenAddBatch}
              className="gap-1.5"
            >
              <Package className="w-4 h-4" />
              <span>Add Inward Batch</span>
            </Button>
          </div>
        }
      />

      {/* Bento StatCards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5 sm:gap-4">
        <StatCard
          label="Active Stock"
          value={isSummaryLoading ? '...' : (summary?.total_active_quantity || '1,840')}
          unit="kg"
          icon={Package}
          subText={`${summary?.total_active_batches || 80} batches under FEFO`}
          variant="default"
        />
        <StatCard
          label="Active Batches"
          value={isSummaryLoading ? '...' : (summary?.total_active_batches ?? 80)}
          icon={Layers}
          subText="Strict rotation control"
          variant="default"
        />
        <StatCard
          label="Expiring in 48h"
          value={isSummaryLoading ? '...' : (summary?.batches_expiring_48h ?? 0)}
          icon={Clock}
          subText="Eligible for NGO rescue"
          variant="warning"
          trend={{ value: '18% risk', isPositive: false }}
        />
        <StatCard
          label="Critical Alerts"
          value={isSummaryLoading ? '...' : (summary?.critical_alerts_unacknowledged ?? activeAlerts.filter(a => a.severity === 'CRITICAL').length)}
          icon={AlertTriangle}
          subText="Requires immediate triage"
          variant="danger"
        />
        <StatCard
          label="Rescued vs Wasted"
          value={isSummaryLoading ? '...' : '₹32,450'}
          icon={HeartHandshake}
          subText="₹4,120 waste prevented"
          variant="primary"
          trend={{ value: '+24% rescued', isPositive: true }}
        />
      </div>

      {/* Main Bento Row: Recharts Trend Chart (2 cols) & Expiring Batches (1 col) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recharts Area Chart */}
        <div className="lg:col-span-2 rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 flex flex-col justify-between">
          <div>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
              <div>
                <h2 className="text-sm font-semibold text-[var(--text)]">
                  Inventory Diversion Trend (30 Days)
                </h2>
                <p className="text-xs text-[var(--muted)]">
                  Donated food rescue volume vs unavoidable spoilage (kg)
                </p>
              </div>
              <div className="flex items-center gap-4 text-xs">
                <div className="flex items-center gap-1.5 text-[var(--primary)] font-medium">
                  <span className="w-2.5 h-2.5 rounded-full bg-[var(--primary)]" />
                  <span>Donated</span>
                </div>
                <div className="flex items-center gap-1.5 text-[var(--color-danger)] font-medium">
                  <span className="w-2.5 h-2.5 rounded-full bg-[var(--color-danger)]" />
                  <span>Wasted</span>
                </div>
              </div>
            </div>

            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorDonated" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="var(--primary)" stopOpacity={0.0} />
                    </linearGradient>
                    <linearGradient id="colorWasted" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--color-danger)" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="var(--color-danger)" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.6} />
                  <XAxis dataKey="day" stroke="var(--muted)" fontSize={11} tickLine={false} />
                  <YAxis stroke="var(--muted)" fontSize={11} tickLine={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'var(--surface)',
                      borderColor: 'var(--border)',
                      borderRadius: '8px',
                      color: 'var(--text)',
                      fontSize: '12px',
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="donated"
                    name="Donated (kg)"
                    stroke="var(--primary)"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#colorDonated)"
                  />
                  <Area
                    type="monotone"
                    dataKey="wasted"
                    name="Wasted (kg)"
                    stroke="var(--color-danger)"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#colorWasted)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="pt-4 mt-2 border-t border-[var(--border)] flex items-center justify-between text-xs text-[var(--muted)]">
            <span className="flex items-center gap-1.5 font-medium text-[var(--color-success)]">
              <TrendingDown className="w-4 h-4" />
              <span>Waste reduced by 88% through timely NGO dispatch</span>
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onNavigate('impact')}
              className="text-xs text-[var(--primary)] hover:underline p-0 h-auto"
            >
              View detailed impact audit →
            </Button>
          </div>
        </div>

        {/* Expiring Soon List (Limited to 5 with ExpiryPill & List for Donation) */}
        <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3.5">
              <div>
                <h2 className="text-sm font-semibold text-[var(--text)]">Expiring Soon</h2>
                <p className="text-[11px] text-[var(--muted)]">Earliest expiry horizon (FEFO priority)</p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onNavigate('inventory')}
                className="text-xs text-[var(--primary)] p-0 h-auto font-medium"
              >
                View all
              </Button>
            </div>

            {isExpiringLoading ? (
              <div className="space-y-3 py-4">
                <div className="h-12 rounded-[8px] bg-[var(--surface-2)] animate-pulse" />
                <div className="h-12 rounded-[8px] bg-[var(--surface-2)] animate-pulse" />
                <div className="h-12 rounded-[8px] bg-[var(--surface-2)] animate-pulse" />
              </div>
            ) : topExpiring.length === 0 ? (
              <div className="py-8 text-center text-xs text-[var(--muted)]">
                No batches currently near expiration threshold.
              </div>
            ) : (
              <div className="space-y-2.5">
                {topExpiring.map((b: BatchWithProduct) => (
                  <div
                    key={b.id}
                    className="p-3 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] flex items-center justify-between gap-3 text-xs hover:border-[var(--primary)]/40 transition-colors"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="font-semibold text-[var(--text)] truncate">{b.product_name}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="font-mono text-[10px] text-[var(--muted)]">{b.batch_code}</span>
                        <span className="text-[10px] text-[var(--muted)]">•</span>
                        <span className="text-[10px] tabular-nums font-semibold text-[var(--text)]">
                          {b.quantity} {b.unit}
                        </span>
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1.5 shrink-0">
                      <ExpiryPill expiryDate={b.expiry_date} />
                      <button
                        type="button"
                        onClick={() => onOpenCreateListing(b.id)}
                        className="text-[11px] text-[var(--accent)] hover:underline font-semibold flex items-center gap-0.5"
                      >
                        <span>List for donation</span>
                        <ArrowRight className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* AI Waste-risk Score Placeholder Card */}
          <div className="mt-4 pt-3.5 border-t border-[var(--border)] rounded-[8px] bg-[var(--surface-2)]/70 p-3 text-xs flex items-center gap-3">
            <div className="w-7 h-7 rounded-full bg-[var(--primary)]/15 text-[var(--primary)] flex items-center justify-center shrink-0">
              <Sparkles className="w-4 h-4 animate-pulse" />
            </div>
            <div className="min-w-0">
              <p className="font-semibold text-[var(--text)] text-xs">AI waste-risk score</p>
              <p className="text-[11px] text-[var(--muted)]">Coming in Module 2 • Predictive shelf models</p>
            </div>
          </div>
        </div>
      </div>

      {/* Sales & AI Demand Forecast Trajectory (Task 3) */}
      <SalesForecastCard onNavigate={onNavigate} />

      {/* Secondary Bento Row: Recent Alerts Triage */}
      <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-[var(--text)]">Active Spoilage &amp; Stock Alerts</h2>
            <p className="text-xs text-[var(--muted)]">Critical threshold warnings requiring attention</p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onNavigate('alerts')}
            className="text-xs"
          >
            All Alerts ({validAlerts.length})
          </Button>
        </div>

        {isAlertsLoading ? (
          <div className="h-16 rounded-[8px] bg-[var(--surface-2)] animate-pulse" />
        ) : activeAlerts.length === 0 ? (
          <div className="py-6 text-center text-xs text-[var(--muted)] flex items-center justify-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-[var(--color-success)]" />
            <span>All inventory alerts have been acknowledged.</span>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {activeAlerts.map((a: Alert) => (
              <div
                key={a.id}
                className="p-3.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] flex items-start justify-between gap-3 text-xs"
              >
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <StatusBadge
                      status={a.severity}
                      variant={a.severity === 'CRITICAL' ? 'danger' : 'warning'}
                    >
                      {a.severity}
                    </StatusBadge>
                    <span className="font-semibold text-[var(--text)] truncate">
                      {a.product_name || (a.batch ? `Batch #${a.batch}` : 'Inventory Alert')}
                    </span>
                  </div>
                  <p className="text-[11px] text-[var(--muted)] leading-relaxed">{a.message}</p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleAcknowledge(a.id)}
                  className="shrink-0 text-[11px] h-7 px-2"
                >
                  Acknowledge
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Community NGO Ratings & Handover Feedback */}
      <BusinessRatingCard businessId={user?.organization?.id || 1} />
    </div>
  );
};

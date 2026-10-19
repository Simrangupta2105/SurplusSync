import React, { useState } from 'react';
import {
  Building2,
  Users,
  ShieldAlert,
  AlertTriangle,
  TrendingUp,
  UtensilsCrossed,
  Star,
  CheckCircle2,
  XCircle,
  ArrowRight,
  ExternalLink,
  RefreshCw,
  Clock,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from 'recharts';
import { StatCard } from '../../components/ui/StatCard';
import { PageHeader } from '../../components/ui/PageHeader';
import { Button } from '../../components/ui/Button';
import { Skeleton } from '../../components/ui/Skeleton';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import {
  useAdminStats,
  useVerifyOrganization,
  useRejectOrganization,
} from '../../hooks/useData';

interface AdminOverviewPageProps {
  onNavigate: (path: string) => void;
  onTriggerToast?: (message: string) => void;
}

export const AdminOverviewPage: React.FC<AdminOverviewPageProps> = ({
  onNavigate,
  onTriggerToast,
}) => {
  const { data: stats, isLoading, isRefetching, refetch } = useAdminStats();
  const verifyOrgMutation = useVerifyOrganization();
  const rejectOrgMutation = useRejectOrganization();

  // Verification dialog states
  const [approveOrgId, setApproveOrgId] = useState<number | null>(null);
  const [rejectOrgId, setRejectOrgId] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState<string>('');

  const handleApprove = async () => {
    if (!approveOrgId) return;
    try {
      await verifyOrgMutation.mutateAsync({ id: approveOrgId });
      onTriggerToast?.('NGO verified and activated successfully.');
      setApproveOrgId(null);
    } catch {
      onTriggerToast?.('Failed to verify NGO.');
    }
  };

  const handleReject = async () => {
    if (!rejectOrgId || !rejectReason.trim()) return;
    try {
      await rejectOrgMutation.mutateAsync({ id: rejectOrgId, reason: rejectReason.trim() });
      onTriggerToast?.('NGO registration rejected.');
      setRejectOrgId(null);
      setRejectReason('');
    } catch {
      onTriggerToast?.('Failed to reject NGO.');
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6 animate-in fade-in duration-200">
        <PageHeader
          title="Platform Administration"
          subtitle="Real-time oversight across Businesses and NGO relief networks"
        />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Skeleton variant="statCard" />
          <Skeleton variant="statCard" />
          <Skeleton variant="statCard" />
          <Skeleton variant="statCard" />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 h-72 rounded-[12px] bg-[var(--surface-2)] animate-pulse" />
          <div className="h-72 rounded-[12px] bg-[var(--surface-2)] animate-pulse" />
        </div>
      </div>
    );
  }

  const signupData = (stats?.signups_per_week || []).map((item) => ({
    name: item.label || item.week,
    Businesses: item.businesses || 0,
    NGOs: item.ngos || 0,
    Total: item.signups ?? item.total ?? item.count ?? 0,
  }));

  const pendingQueue = stats?.needs_approval_queue || [];
  const openIssuesQueue = stats?.open_issues_queue || [];

  return (
    <div className="space-y-6 pb-8 animate-in fade-in duration-150">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <PageHeader
          title="Platform Administration"
          subtitle="Central control cockpit for verification, incident reporting, and platform ratings"
        />
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isRefetching}
            className="text-xs h-9"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 mr-1.5 ${isRefetching ? 'animate-spin' : ''}`}
            />
            {isRefetching ? 'Syncing...' : 'Refresh'}
          </Button>
        </div>
      </div>

      {/* Top Stat Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Registered Businesses"
          value={stats?.total_businesses ?? 0}
          icon={Building2}
          subtitle="Active surplus donors"
        />
        <StatCard
          label="Registered NGOs"
          value={stats?.total_ngos ?? 0}
          icon={Users}
          subtitle="Food relief organizations"
        />
        <StatCard
          label="Pending Verifications"
          value={stats?.pending_verifications ?? stats?.pending_ngo_verifications ?? 0}
          icon={ShieldAlert}
          variant={(stats?.pending_verifications ?? 0) > 0 ? 'warning' : 'default'}
          subtitle="Awaiting admin clearance"
        />
        <StatCard
          label="Open Issues"
          value={stats?.open_issues ?? 0}
          icon={AlertTriangle}
          variant={(stats?.open_issues ?? 0) > 0 ? 'danger' : 'default'}
          subtitle="Unresolved disputes & tickets"
        />
      </div>

      {/* Secondary Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-[var(--muted)] font-medium">Total Food Rescued</p>
            <p className="text-xl font-bold text-[var(--text)] mt-1">
              {Number(stats?.total_kg_donated ?? 0).toLocaleString()} <span className="text-xs font-normal text-[var(--muted)]">kg</span>
            </p>
          </div>
          <div className="w-10 h-10 rounded-full bg-[var(--primary)]/10 text-[var(--primary)] flex items-center justify-center">
            <TrendingUp className="w-5 h-5" />
          </div>
        </div>

        <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-[var(--muted)] font-medium">Active Surplus Listings</p>
            <p className="text-xl font-bold text-[var(--text)] mt-1">
              {stats?.active_listings ?? 0}
            </p>
          </div>
          <div className="w-10 h-10 rounded-full bg-[var(--color-info-bg)] text-[var(--color-info)] flex items-center justify-center">
            <UtensilsCrossed className="w-5 h-5" />
          </div>
        </div>

        <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-[var(--muted)] font-medium">Platform Rating Avg</p>
            <p className="text-xl font-bold text-[var(--text)] mt-1 flex items-center gap-1.5">
              <span>{stats?.average_platform_rating ?? stats?.average_rating ?? 5.0}</span>
              <span className="text-xs text-amber-500 flex items-center">
                ★ <span className="text-[var(--muted)] ml-1">({stats?.total_ratings ?? 12})</span>
              </span>
            </p>
          </div>
          <div className="w-10 h-10 rounded-full bg-amber-500/10 text-amber-500 flex items-center justify-center">
            <Star className="w-5 h-5 fill-amber-500" />
          </div>
        </div>
      </div>

      {/* Main Row: Growth Chart & Quick Queues */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Weekly Registrations Bar Chart (2 cols) */}
        <div className="lg:col-span-2 rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 flex flex-col justify-between">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-[var(--text)]">Weekly Platform Registrations</h3>
              <p className="text-xs text-[var(--muted)]">New businesses and NGOs onboarding per week</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 text-xs text-[var(--muted)]">
                <span className="w-2.5 h-2.5 rounded-full bg-[var(--primary)]" /> Businesses
              </span>
              <span className="inline-flex items-center gap-1.5 text-xs text-[var(--muted)] ml-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[#10b981]" /> NGOs
              </span>
            </div>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={signupData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="name" stroke="var(--muted)" fontSize={11} tickLine={false} />
                <YAxis stroke="var(--muted)" fontSize={11} tickLine={false} allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'var(--surface)',
                    borderColor: 'var(--border)',
                    borderRadius: '8px',
                    color: 'var(--text)',
                    fontSize: '12px',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
                  }}
                  cursor={{ fill: 'var(--surface-2)', opacity: 0.5 }}
                />
                <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                <Bar dataKey="Businesses" fill="var(--primary)" radius={[4, 4, 0, 0]} maxBarSize={32} />
                <Bar dataKey="NGOs" fill="#10b981" radius={[4, 4, 0, 0]} maxBarSize={32} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Action Queues (1 col) */}
        <div className="space-y-6">
          {/* Needs Approval Queue */}
          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-amber-500" />
                <h3 className="text-sm font-semibold text-[var(--text)]">Needs Approval</h3>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onNavigate('admin/verifications')}
                className="text-xs h-7 px-2 text-[var(--primary)]"
              >
                View all <ArrowRight className="w-3 h-3 ml-1" />
              </Button>
            </div>

            {pendingQueue.length === 0 ? (
              <div className="py-6 text-center text-xs text-[var(--muted)]">
                <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2 opacity-80" />
                All NGO verifications are up to date.
              </div>
            ) : (
              <div className="space-y-3">
                {pendingQueue.slice(0, 3).map((ngo) => (
                  <div
                    key={ngo.id}
                    className="p-3 rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] flex flex-col gap-2"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="text-xs font-semibold text-[var(--text)]">{ngo.name}</p>
                        <p className="text-[11px] text-[var(--muted)] truncate max-w-[180px]">
                          {ngo.address || ngo.phone || 'New NGO applicant'}
                        </p>
                      </div>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-500 font-medium">
                        Pending
                      </span>
                    </div>
                    <div className="flex items-center justify-end gap-1.5 pt-1 border-t border-[var(--border)]/50">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setRejectOrgId(ngo.id)}
                        className="text-[11px] h-6 px-2 text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10"
                      >
                        Reject
                      </Button>
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => setApproveOrgId(ngo.id)}
                        className="text-[11px] h-6 px-2"
                      >
                        Verify
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Open Issues Queue */}
          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-[var(--color-danger)]" />
                <h3 className="text-sm font-semibold text-[var(--text)]">Urgent Issues</h3>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onNavigate('admin/issues')}
                className="text-xs h-7 px-2 text-[var(--primary)]"
              >
                View all <ArrowRight className="w-3 h-3 ml-1" />
              </Button>
            </div>

            {openIssuesQueue.length === 0 ? (
              <div className="py-6 text-center text-xs text-[var(--muted)]">
                <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2 opacity-80" />
                No unresolved tickets reported.
              </div>
            ) : (
              <div className="space-y-3">
                {openIssuesQueue.slice(0, 3).map((issue) => (
                  <div
                    key={issue.id}
                    className="p-3 rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] flex flex-col gap-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                          issue.priority === 'CRITICAL'
                            ? 'bg-red-500/10 text-red-500'
                            : issue.priority === 'HIGH'
                            ? 'bg-amber-500/10 text-amber-500'
                            : 'bg-blue-500/10 text-blue-500'
                        }`}
                      >
                        {issue.priority}
                      </span>
                      <span className="text-[11px] text-[var(--muted)]">
                        {issue.reporter_org__name || 'Platform user'}
                      </span>
                    </div>
                    <p className="text-xs text-[var(--text)] font-medium line-clamp-2">
                      {issue.description}
                    </p>
                    <div className="flex justify-end pt-1">
                      <button
                        onClick={() => onNavigate('admin/issues')}
                        className="text-[11px] font-semibold text-[var(--primary)] hover:underline inline-flex items-center"
                      >
                        Inspect ticket <ExternalLink className="w-3 h-3 ml-1" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Quick Navigation Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-2">
        <div
          onClick={() => onNavigate('admin/verifications')}
          className="p-4 rounded-[12px] border border-[var(--border)] bg-[var(--surface)] hover:border-[var(--primary)] cursor-pointer transition-all flex items-center justify-between group"
        >
          <div>
            <p className="text-xs font-bold text-[var(--text)] group-hover:text-[var(--primary)]">
              Verifications Queue
            </p>
            <p className="text-[11px] text-[var(--muted)]">Inspect NGO compliance</p>
          </div>
          <ArrowRight className="w-4 h-4 text-[var(--muted)] group-hover:translate-x-1 group-hover:text-[var(--primary)] transition-all" />
        </div>

        <div
          onClick={() => onNavigate('admin/organizations')}
          className="p-4 rounded-[12px] border border-[var(--border)] bg-[var(--surface)] hover:border-[var(--primary)] cursor-pointer transition-all flex items-center justify-between group"
        >
          <div>
            <p className="text-xs font-bold text-[var(--text)] group-hover:text-[var(--primary)]">
              All Organizations
            </p>
            <p className="text-[11px] text-[var(--muted)]">Manage Businesses & NGOs</p>
          </div>
          <ArrowRight className="w-4 h-4 text-[var(--muted)] group-hover:translate-x-1 group-hover:text-[var(--primary)] transition-all" />
        </div>

        <div
          onClick={() => onNavigate('admin/ratings')}
          className="p-4 rounded-[12px] border border-[var(--border)] bg-[var(--surface)] hover:border-[var(--primary)] cursor-pointer transition-all flex items-center justify-between group"
        >
          <div>
            <p className="text-xs font-bold text-[var(--text)] group-hover:text-[var(--primary)]">
              Ratings Moderation
            </p>
            <p className="text-[11px] text-[var(--muted)]">Review & moderate feedback</p>
          </div>
          <ArrowRight className="w-4 h-4 text-[var(--muted)] group-hover:translate-x-1 group-hover:text-[var(--primary)] transition-all" />
        </div>

        <div
          onClick={() => onNavigate('admin/audit-logs')}
          className="p-4 rounded-[12px] border border-[var(--border)] bg-[var(--surface)] hover:border-[var(--primary)] cursor-pointer transition-all flex items-center justify-between group"
        >
          <div>
            <p className="text-xs font-bold text-[var(--text)] group-hover:text-[var(--primary)]">
              Platform Audit Logs
            </p>
            <p className="text-[11px] text-[var(--muted)]">Append-only security records</p>
          </div>
          <ArrowRight className="w-4 h-4 text-[var(--muted)] group-hover:translate-x-1 group-hover:text-[var(--primary)] transition-all" />
        </div>
      </div>

      {/* Confirm Approve Dialog */}
      <ConfirmDialog
        isOpen={!!approveOrgId}
        title="Approve NGO Verification"
        description="This will verify the organization, activate their food rescue claiming privileges, and send a confirmation email."
        confirmLabel="Verify & Activate"
        variant="primary"
        isLoading={verifyOrgMutation.isPending}
        onConfirm={handleApprove}
        onCancel={() => setApproveOrgId(null)}
      />

      {/* Reject Dialog with Mandatory Reason */}
      {rejectOrgId && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150"
        >
          <div className="w-full max-w-md rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-red-500/10 text-red-500 flex items-center justify-center">
                <XCircle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-[var(--text)]">Reject NGO Verification</h3>
                <p className="text-xs text-[var(--muted)]">Please state the rejection reason</p>
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--text)] block mb-1">
                Rejection Reason (Required)
              </label>
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="e.g., Incomplete NGO registration certificate or unverified contact address."
                rows={3}
                className="w-full text-xs rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setRejectOrgId(null);
                  setRejectReason('');
                }}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                disabled={!rejectReason.trim() || rejectOrgMutation.isPending}
                onClick={handleReject}
              >
                {rejectOrgMutation.isPending ? 'Rejecting...' : 'Confirm Rejection'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

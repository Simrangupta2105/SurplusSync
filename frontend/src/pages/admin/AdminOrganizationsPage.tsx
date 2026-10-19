import React, { useState } from 'react';
import {
  Building2,
  Users,
  Search,
  Filter,
  Ban,
  RotateCcw,
  Eye,
  CheckCircle2,
  XCircle,
  Clock,
  UserCheck,
} from 'lucide-react';
import { PageHeader } from '../../components/ui/PageHeader';
import { Button } from '../../components/ui/Button';
import { Sheet } from '../../components/ui/Sheet';
import { Skeleton } from '../../components/ui/Skeleton';
import { EmptyState } from '../../components/ui/EmptyState';

import {
  useAdminOrganizations,
  useAdminOrganization,
  useSuspendOrganization,
  useReinstateOrganization,
  useVerifyOrganization,
  useRejectOrganization,
} from '../../hooks/useData';
import type { AdminOrganization, VerificationStatus } from '../../types';

interface AdminOrganizationsPageProps {
  onTriggerToast?: (message: string) => void;
}

export const AdminOrganizationsPage: React.FC<AdminOrganizationsPageProps> = ({
  onTriggerToast,
}) => {
  const [activeTab, setActiveTab] = useState<'ALL' | 'BUSINESS' | 'NGO'>('ALL');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [search, setSearch] = useState('');
  const [selectedOrgId, setSelectedOrgId] = useState<number | null>(null);

  // Queries
  const { data: orgsResponse, isLoading } = useAdminOrganizations({
    org_type: activeTab === 'ALL' ? undefined : activeTab,
    verification_status: statusFilter === 'ALL' ? undefined : statusFilter,
    search: search.trim() || undefined,
  });

  const { data: selectedOrgDetail, isLoading: isLoadingDetail } =
    useAdminOrganization(selectedOrgId || 0);

  // Mutations
  const suspendMutation = useSuspendOrganization();
  const reinstateMutation = useReinstateOrganization();
  const verifyMutation = useVerifyOrganization();
  const rejectMutation = useRejectOrganization();

  // Action dialog states
  const [actionType, setActionType] = useState<
    'SUSPEND' | 'REINSTATE' | 'VERIFY' | 'REJECT' | null
  >(null);
  const [actionReason, setActionReason] = useState('');
  const [targetOrg, setTargetOrg] = useState<AdminOrganization | null>(null);

  const organizations = orgsResponse?.results || [];

  const handleAction = async () => {
    if (!targetOrg || !actionType) return;
    try {
      if (actionType === 'SUSPEND') {
        await suspendMutation.mutateAsync({
          id: targetOrg.id,
          reason: actionReason.trim() || undefined,
        });
        onTriggerToast?.(`Suspended ${targetOrg.name}.`);
      } else if (actionType === 'REINSTATE') {
        await reinstateMutation.mutateAsync({
          id: targetOrg.id,
          reason: actionReason.trim() || undefined,
        });
        onTriggerToast?.(`Reinstated ${targetOrg.name}.`);
      } else if (actionType === 'VERIFY') {
        await verifyMutation.mutateAsync({
          id: targetOrg.id,
          note: actionReason.trim() || undefined,
        });
        onTriggerToast?.(`Verified ${targetOrg.name}.`);
      } else if (actionType === 'REJECT') {
        if (!actionReason.trim()) {
          onTriggerToast?.('A rejection reason is required.');
          return;
        }
        await rejectMutation.mutateAsync({
          id: targetOrg.id,
          reason: actionReason.trim(),
        });
        onTriggerToast?.(`Rejected ${targetOrg.name}.`);
      }
      setActionType(null);
      setActionReason('');
      setTargetOrg(null);
    } catch {
      onTriggerToast?.(`Failed to execute ${actionType.toLowerCase()} action.`);
    }
  };

  const getStatusBadge = (status: VerificationStatus, isVerified: boolean) => {
    switch (status) {
      case 'VERIFIED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-500">
            <CheckCircle2 className="w-3 h-3" /> Verified
          </span>
        );
      case 'PENDING':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-500">
            <Clock className="w-3 h-3" /> Pending
          </span>
        );
      case 'SUSPENDED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-red-500/10 text-red-500">
            <Ban className="w-3 h-3" /> Suspended
          </span>
        );
      case 'REJECTED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-neutral-500/10 text-neutral-400">
            <XCircle className="w-3 h-3" /> Rejected
          </span>
        );
      default:
        return isVerified ? (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-500">
            Verified
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-500">
            Pending
          </span>
        );
    }
  };

  return (
    <div className="space-y-6 pb-8 animate-in fade-in duration-150">
      <PageHeader
        title="Organizations Directory"
        subtitle="Manage Businesses and NGO partners across the SurplusSync network"
      />

      {/* Tabs & Controls */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 bg-[var(--surface)] p-3 rounded-[12px] border border-[var(--border)]">
        {/* Role Tabs */}
        <div className="flex items-center gap-1 p-1 bg-[var(--surface-2)] rounded-[8px] w-fit">
          <button
            onClick={() => setActiveTab('ALL')}
            className={`px-3 py-1.5 rounded-[6px] text-xs font-semibold transition-all ${
              activeTab === 'ALL'
                ? 'bg-[var(--surface)] text-[var(--text)] shadow-xs'
                : 'text-[var(--muted)] hover:text-[var(--text)]'
            }`}
          >
            All Organizations
          </button>
          <button
            onClick={() => setActiveTab('BUSINESS')}
            className={`px-3 py-1.5 rounded-[6px] text-xs font-semibold transition-all flex items-center gap-1.5 ${
              activeTab === 'BUSINESS'
                ? 'bg-[var(--surface)] text-[var(--text)] shadow-xs'
                : 'text-[var(--muted)] hover:text-[var(--text)]'
            }`}
          >
            <Building2 className="w-3.5 h-3.5" />
            Businesses
          </button>
          <button
            onClick={() => setActiveTab('NGO')}
            className={`px-3 py-1.5 rounded-[6px] text-xs font-semibold transition-all flex items-center gap-1.5 ${
              activeTab === 'NGO'
                ? 'bg-[var(--surface)] text-[var(--text)] shadow-xs'
                : 'text-[var(--muted)] hover:text-[var(--text)]'
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            NGOs
          </button>
        </div>

        {/* Search & Status Filter */}
        <div className="flex flex-col sm:flex-row items-center gap-2.5">
          <div className="relative w-full sm:w-64">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
            <input
              type="text"
              placeholder="Search organizations..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full text-xs pl-9 pr-3 py-1.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Filter className="w-4 h-4 text-[var(--muted)] shrink-0 hidden sm:block" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-xs px-3 py-1.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)] w-full sm:w-auto"
            >
              <option value="ALL">All Statuses</option>
              <option value="VERIFIED">Verified</option>
              <option value="PENDING">Pending</option>
              <option value="SUSPENDED">Suspended</option>
              <option value="REJECTED">Rejected</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Content: Table on Desktop, Cards on Mobile */}
      {isLoading ? (
        <div className="space-y-3">
          <Skeleton variant="card" className="h-16" />
          <Skeleton variant="card" className="h-16" />
          <Skeleton variant="card" className="h-16" />
        </div>
      ) : organizations.length === 0 ? (
        <div className="bg-[var(--surface)] rounded-[12px] border border-[var(--border)] p-12">
          <EmptyState
            icon={Building2}
            title="No organizations found"
            description="No businesses or NGOs match your search criteria or selected filters."
          />
        </div>
      ) : (
        <>
          {/* Desktop Table View (>= md) */}
          <div className="hidden md:block rounded-[12px] border border-[var(--border)] bg-[var(--surface)] overflow-hidden shadow-xs">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[var(--border)] bg-[var(--surface-2)] text-[11px] font-bold uppercase tracking-wider text-[var(--muted)]">
                  <th className="px-5 py-3.5">Organization</th>
                  <th className="px-5 py-3.5">Type</th>
                  <th className="px-5 py-3.5">Status</th>
                  <th className="px-5 py-3.5">Contact</th>
                  <th className="px-5 py-3.5">Created</th>
                  <th className="px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)] text-xs">
                {organizations.map((org) => (
                  <tr
                    key={org.id}
                    className="hover:bg-[var(--surface-2)]/60 transition-colors cursor-pointer group"
                    onClick={() => setSelectedOrgId(org.id)}
                  >
                    <td className="px-5 py-4">
                      <div>
                        <p className="font-bold text-[var(--text)] group-hover:text-[var(--primary)] transition-colors">
                          {org.name}
                        </p>
                        <p className="text-[11px] text-[var(--muted)]">ID #{org.id}</p>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                          org.org_type === 'BUSINESS'
                            ? 'bg-blue-500/10 text-blue-500'
                            : 'bg-emerald-500/10 text-emerald-500'
                        }`}
                      >
                        {org.org_type === 'BUSINESS' ? (
                          <Building2 className="w-3 h-3" />
                        ) : (
                          <Users className="w-3 h-3" />
                        )}
                        {org.org_type}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      {getStatusBadge(org.verification_status, org.is_verified)}
                    </td>
                    <td className="px-5 py-4 text-[var(--muted)]">
                      <p className="truncate max-w-[200px]">{org.address || '—'}</p>
                      <p className="text-[11px]">{org.phone || '—'}</p>
                    </td>
                    <td className="px-5 py-4 text-[var(--muted)] whitespace-nowrap">
                      {new Date(org.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-5 py-4 text-right" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center justify-end gap-1.5">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedOrgId(org.id)}
                          className="text-xs h-7 px-2 text-[var(--muted)] hover:text-[var(--text)]"
                          title="Inspect Details"
                        >
                          <Eye className="w-3.5 h-3.5 mr-1" /> View
                        </Button>

                        {org.verification_status !== 'SUSPENDED' ? (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setTargetOrg(org);
                              setActionType('SUSPEND');
                              setActionReason('');
                            }}
                            className="text-xs h-7 px-2 text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10 border-[var(--color-danger)]/30"
                            title="Suspend Organization"
                          >
                            <Ban className="w-3.5 h-3.5 mr-1" /> Suspend
                          </Button>
                        ) : (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setTargetOrg(org);
                              setActionType('REINSTATE');
                              setActionReason('');
                            }}
                            className="text-xs h-7 px-2 text-emerald-500 hover:bg-emerald-500/10 border-emerald-500/30"
                            title="Reinstate Organization"
                          >
                            <RotateCcw className="w-3.5 h-3.5 mr-1" /> Reinstate
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile Card List View (< md) */}
          <div className="grid grid-cols-1 gap-3 md:hidden">
            {organizations.map((org) => (
              <div
                key={org.id}
                onClick={() => setSelectedOrgId(org.id)}
                className="bg-[var(--surface)] p-4 rounded-[12px] border border-[var(--border)] shadow-xs space-y-3"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-[var(--text)]">{org.name}</h3>
                    <p className="text-[11px] text-[var(--muted)]">ID #{org.id}</p>
                  </div>
                  {getStatusBadge(org.verification_status, org.is_verified)}
                </div>

                <div className="flex items-center gap-2 text-xs text-[var(--muted)]">
                  <span
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold ${
                      org.org_type === 'BUSINESS'
                        ? 'bg-blue-500/10 text-blue-500'
                        : 'bg-emerald-500/10 text-emerald-500'
                    }`}
                  >
                    {org.org_type}
                  </span>
                  <span>•</span>
                  <span>{org.phone || 'No phone'}</span>
                </div>

                <p className="text-xs text-[var(--muted)] truncate">{org.address || 'No address'}</p>

                <div className="flex items-center justify-between pt-2 border-t border-[var(--border)]" onClick={(e) => e.stopPropagation()}>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedOrgId(org.id)}
                    className="text-xs h-7 px-2"
                  >
                    <Eye className="w-3 h-3 mr-1" /> Inspect
                  </Button>

                  {org.verification_status !== 'SUSPENDED' ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setTargetOrg(org);
                        setActionType('SUSPEND');
                        setActionReason('');
                      }}
                      className="text-xs h-7 px-2 text-[var(--color-danger)]"
                    >
                      <Ban className="w-3 h-3 mr-1" /> Suspend
                    </Button>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setTargetOrg(org);
                        setActionType('REINSTATE');
                        setActionReason('');
                      }}
                      className="text-xs h-7 px-2 text-emerald-500"
                    >
                      <RotateCcw className="w-3 h-3 mr-1" /> Reinstate
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Organization Detail Drawer Sheet */}
      <Sheet
        isOpen={!!selectedOrgId}
        onClose={() => setSelectedOrgId(null)}
        title={selectedOrgDetail?.name || 'Organization Details'}
        description={`ID #${selectedOrgId} • ${selectedOrgDetail?.org_type || 'Organization'}`}
        width="lg"
        footer={
          selectedOrgDetail && (
            <div className="flex items-center justify-between w-full">
              <div>
                {getStatusBadge(
                  selectedOrgDetail.verification_status,
                  selectedOrgDetail.is_verified
                )}
              </div>
              <div className="flex items-center gap-2">
                {selectedOrgDetail.verification_status === 'PENDING' && (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setTargetOrg(selectedOrgDetail);
                        setActionType('REJECT');
                        setActionReason('');
                      }}
                      className="text-xs text-[var(--color-danger)]"
                    >
                      Reject
                    </Button>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => {
                        setTargetOrg(selectedOrgDetail);
                        setActionType('VERIFY');
                        setActionReason('');
                      }}
                      className="text-xs"
                    >
                      Verify
                    </Button>
                  </>
                )}

                {selectedOrgDetail.verification_status !== 'SUSPENDED' &&
                  selectedOrgDetail.verification_status !== 'PENDING' && (
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => {
                        setTargetOrg(selectedOrgDetail);
                        setActionType('SUSPEND');
                        setActionReason('');
                      }}
                      className="text-xs"
                    >
                      <Ban className="w-3.5 h-3.5 mr-1" /> Suspend Organization
                    </Button>
                  )}

                {selectedOrgDetail.verification_status === 'SUSPENDED' && (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => {
                      setTargetOrg(selectedOrgDetail);
                      setActionType('REINSTATE');
                      setActionReason('');
                    }}
                    className="text-xs bg-emerald-600 hover:bg-emerald-700"
                  >
                    <RotateCcw className="w-3.5 h-3.5 mr-1" /> Reinstate Organization
                  </Button>
                )}
              </div>
            </div>
          )
        }
      >
        {isLoadingDetail || !selectedOrgDetail ? (
          <div className="space-y-4 py-4">
            <Skeleton variant="card" className="h-24" />
            <Skeleton variant="card" className="h-32" />
            <Skeleton variant="card" className="h-48" />
          </div>
        ) : (
          <div className="space-y-6 py-2 text-xs">
            {/* Overview Card */}
            <div className="p-4 rounded-[10px] bg-[var(--surface-2)] border border-[var(--border)] space-y-3">
              <h4 className="font-bold text-sm text-[var(--text)]">Profile & Contact</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-[var(--muted)]">
                <div>
                  <span className="font-semibold text-[var(--text)] block">Address:</span>
                  <span>{selectedOrgDetail.address || 'None provided'}</span>
                </div>
                <div>
                  <span className="font-semibold text-[var(--text)] block">Phone:</span>
                  <span>{selectedOrgDetail.phone || 'None provided'}</span>
                </div>
                <div>
                  <span className="font-semibold text-[var(--text)] block">Coordinates:</span>
                  <span>
                    {selectedOrgDetail.latitude !== null && selectedOrgDetail.longitude !== null
                      ? `${selectedOrgDetail.latitude.toFixed(4)}, ${selectedOrgDetail.longitude.toFixed(4)}`
                      : 'None provided'}
                  </span>
                </div>
                <div>
                  <span className="font-semibold text-[var(--text)] block">Joined:</span>
                  <span>{new Date(selectedOrgDetail.created_at).toLocaleString()}</span>
                </div>
              </div>
              {selectedOrgDetail.verification_note && (
                <div className="pt-2 border-t border-[var(--border)]">
                  <span className="font-semibold text-[var(--text)] block">Verification Note:</span>
                  <span className="italic">{selectedOrgDetail.verification_note}</span>
                </div>
              )}
            </div>

            {/* Users list */}
            <div>
              <h4 className="font-bold text-sm text-[var(--text)] mb-2 flex items-center gap-1.5">
                <UserCheck className="w-4 h-4 text-[var(--primary)]" />
                Associated Users ({selectedOrgDetail.users?.length || 0})
              </h4>
              <div className="rounded-[8px] border border-[var(--border)] overflow-hidden divide-y divide-[var(--border)] bg-[var(--surface)]">
                {(selectedOrgDetail.users || []).map((u) => (
                  <div key={u.id} className="p-3 flex items-center justify-between">
                    <div>
                      <p className="font-semibold text-[var(--text)]">{u.username}</p>
                      <p className="text-[11px] text-[var(--muted)]">{u.email}</p>
                    </div>
                    <div className="text-right">
                      <span className="px-2 py-0.5 rounded-full bg-[var(--surface-2)] text-[10px] font-bold">
                        {u.role}
                      </span>
                      <p className="text-[10px] text-[var(--muted)] mt-0.5">
                        {u.is_active ? 'Active' : 'Inactive'}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Activity Summary */}
            <div>
              <h4 className="font-bold text-sm text-[var(--text)] mb-2">Recent Records</h4>
              <div className="grid grid-cols-2 gap-2 text-center">
                <div className="p-3 rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)]">
                  <p className="text-lg font-bold text-[var(--text)]">
                    {selectedOrgDetail.recent_activity?.listings?.length ??
                      selectedOrgDetail.listings_count ??
                      0}
                  </p>
                  <p className="text-[11px] text-[var(--muted)]">Donation Listings</p>
                </div>
                <div className="p-3 rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)]">
                  <p className="text-lg font-bold text-[var(--text)]">
                    {selectedOrgDetail.recent_activity?.claims?.length ??
                      selectedOrgDetail.claims_count ??
                      0}
                  </p>
                  <p className="text-[11px] text-[var(--muted)]">Claims Placed</p>
                </div>
              </div>
            </div>
          </div>
        )}
      </Sheet>

      {/* Action Dialog (Suspend / Reinstate / Verify / Reject) */}
      {actionType && targetOrg && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150"
        >
          <div className="w-full max-w-md rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center ${
                  actionType === 'SUSPEND' || actionType === 'REJECT'
                    ? 'bg-red-500/10 text-red-500'
                    : 'bg-emerald-500/10 text-emerald-500'
                }`}
              >
                {actionType === 'SUSPEND' ? (
                  <Ban className="w-5 h-5" />
                ) : actionType === 'REINSTATE' ? (
                  <RotateCcw className="w-5 h-5" />
                ) : actionType === 'VERIFY' ? (
                  <CheckCircle2 className="w-5 h-5" />
                ) : (
                  <XCircle className="w-5 h-5" />
                )}
              </div>
              <div>
                <h3 className="text-sm font-bold text-[var(--text)] capitalize">
                  {actionType.toLowerCase()} {targetOrg.name}
                </h3>
                <p className="text-xs text-[var(--muted)]">
                  {actionType === 'SUSPEND'
                    ? 'Prevents user login and blocks claims/listings'
                    : actionType === 'REINSTATE'
                    ? 'Restores active operational privileges'
                    : actionType === 'VERIFY'
                    ? 'Approves NGO verification status'
                    : 'Rejects registration request'}
                </p>
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--text)] block mb-1">
                {actionType === 'REJECT' ? 'Rejection Reason (Required)' : 'Administrative Reason (Optional)'}
              </label>
              <textarea
                value={actionReason}
                onChange={(e) => setActionReason(e.target.value)}
                placeholder={
                  actionType === 'SUSPEND'
                    ? 'e.g., Unresolved repeated food quality complaints.'
                    : 'Enter audit rationale for this action...'
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
                  setActionType(null);
                  setActionReason('');
                  setTargetOrg(null);
                }}
              >
                Cancel
              </Button>
              <Button
                variant={actionType === 'SUSPEND' || actionType === 'REJECT' ? 'danger' : 'primary'}
                size="sm"
                onClick={handleAction}
              >
                Confirm {actionType.toLowerCase()}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

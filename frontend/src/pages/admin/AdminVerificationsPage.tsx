import React, { useState, useMemo } from 'react';
import {
  ShieldCheck,
  CheckCircle2,
  XCircle,
  MapPin,
  Phone,
  Calendar,
  Search,
  CheckCheck,
  Building2,
} from 'lucide-react';

import { PageHeader } from '../../components/ui/PageHeader';
import { Button } from '../../components/ui/Button';
import { EmptyState } from '../../components/ui/EmptyState';
import { Skeleton } from '../../components/ui/Skeleton';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import {
  useAdminOrganizations,
  useVerifyOrganization,
  useRejectOrganization,
} from '../../hooks/useData';
import type { AdminOrganization } from '../../types';

interface AdminVerificationsPageProps {
  onTriggerToast?: (message: string) => void;
}

export const AdminVerificationsPage: React.FC<AdminVerificationsPageProps> = ({
  onTriggerToast,
}) => {
  const [search, setSearch] = useState('');
  const { data: response, isLoading } = useAdminOrganizations({
    org_type: 'NGO',
    verification_status: 'PENDING',
  });

  const verifyOrgMutation = useVerifyOrganization();
  const rejectOrgMutation = useRejectOrganization();

  // Approve single state
  const [approveOrg, setApproveOrg] = useState<AdminOrganization | null>(null);
  const [approveNote, setApproveNote] = useState('');

  // Reject single state
  const [rejectOrg, setRejectOrg] = useState<AdminOrganization | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  // Bulk approve state
  const [isBulkApproveOpen, setIsBulkApproveOpen] = useState(false);
  const [isBulkProcessing, setIsBulkProcessing] = useState(false);

  const pendingNGOs = useMemo(() => response?.results || [], [response?.results]);


  const filteredNGOs = useMemo(() => {
    if (!search.trim()) return pendingNGOs;
    const q = search.toLowerCase();
    return pendingNGOs.filter(
      (ngo) =>
        ngo.name.toLowerCase().includes(q) ||
        ngo.address.toLowerCase().includes(q) ||
        ngo.phone.toLowerCase().includes(q)
    );
  }, [pendingNGOs, search]);

  const handleApprove = async () => {
    if (!approveOrg) return;
    try {
      await verifyOrgMutation.mutateAsync({
        id: approveOrg.id,
        note: approveNote.trim() || undefined,
      });
      onTriggerToast?.(`Successfully verified ${approveOrg.name}.`);
      setApproveOrg(null);
      setApproveNote('');
    } catch {
      onTriggerToast?.('Failed to verify NGO.');
    }
  };

  const handleReject = async () => {
    if (!rejectOrg || !rejectReason.trim()) return;
    try {
      await rejectOrgMutation.mutateAsync({
        id: rejectOrg.id,
        reason: rejectReason.trim(),
      });
      onTriggerToast?.(`Rejected verification for ${rejectOrg.name}.`);
      setRejectOrg(null);
      setRejectReason('');
    } catch {
      onTriggerToast?.('Failed to reject NGO.');
    }
  };

  const handleBulkApprove = async () => {
    if (pendingNGOs.length === 0) return;
    setIsBulkProcessing(true);
    let successCount = 0;
    try {
      for (const ngo of pendingNGOs) {
        await verifyOrgMutation.mutateAsync({
          id: ngo.id,
          note: 'Bulk verified by Platform Administrator',
        });
        successCount++;
      }
      onTriggerToast?.(`Successfully bulk approved ${successCount} NGOs.`);
      setIsBulkApproveOpen(false);
    } catch {
      onTriggerToast?.(`Bulk approval encountered an error after ${successCount} approvals.`);
    } finally {
      setIsBulkProcessing(false);
    }
  };

  return (
    <div className="space-y-6 pb-8 animate-in fade-in duration-150">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <PageHeader
          title="NGO Verification Queue"
          subtitle="Review official documentation, contact details, and locations to authorize relief operations"
        />
        {pendingNGOs.length > 1 && (
          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsBulkApproveOpen(true)}
            className="text-xs h-9 shrink-0"
          >
            <CheckCheck className="w-4 h-4 mr-1.5" />
            Bulk Approve All ({pendingNGOs.length})
          </Button>
        )}
      </div>

      {/* Search Bar & Counter */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-[var(--surface)] p-3 rounded-[12px] border border-[var(--border)]">
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
          <input
            type="text"
            placeholder="Search pending NGOs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full text-xs pl-9 pr-3 py-2 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
          />
        </div>
        <div className="flex items-center gap-2 text-xs text-[var(--muted)] w-full sm:w-auto justify-end">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-500 font-semibold">
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
            {pendingNGOs.length} awaiting review
          </span>
        </div>
      </div>

      {/* Main Queue List */}
      {isLoading ? (
        <div className="space-y-4">
          <Skeleton variant="card" className="h-32" />
          <Skeleton variant="card" className="h-32" />
          <Skeleton variant="card" className="h-32" />
        </div>
      ) : filteredNGOs.length === 0 ? (
        <div className="bg-[var(--surface)] rounded-[12px] border border-[var(--border)] p-12">
          <EmptyState
            icon={ShieldCheck}
            title={search ? 'No matching pending NGOs' : 'Verification Queue is Clear'}
            description={
              search
                ? 'Try adjusting your search terms.'
                : 'All registered NGO relief partners have been reviewed. New applications will appear here.'
            }
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filteredNGOs.map((ngo) => (
            <div
              key={ngo.id}
              className="bg-[var(--surface)] rounded-[12px] border border-[var(--border)] p-5 transition-all hover:border-[var(--primary)]/50 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-6"
            >
              {/* Organization Info */}
              <div className="space-y-3 flex-1">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-[10px] bg-amber-500/10 text-amber-500 flex items-center justify-center shrink-0">
                    <Building2 className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-bold text-[var(--text)]">{ngo.name}</h3>
                      <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-500">
                        Pending Verification
                      </span>
                    </div>
                    <p className="text-xs text-[var(--muted)]">Organization ID: #{ngo.id}</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs text-[var(--muted)] pt-1">
                  <div className="flex items-center gap-2">
                    <MapPin className="w-3.5 h-3.5 text-[var(--muted)] shrink-0" />
                    <span className="truncate">{ngo.address || 'Address not provided'}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Phone className="w-3.5 h-3.5 text-[var(--muted)] shrink-0" />
                    <span>{ngo.phone || 'Phone not provided'}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Calendar className="w-3.5 h-3.5 text-[var(--muted)] shrink-0" />
                    <span>Applied: {new Date(ngo.created_at).toLocaleDateString()}</span>
                  </div>
                </div>

                {/* Coordinates Pin badge */}
                {ngo.latitude !== null && ngo.longitude !== null && (
                  <div className="inline-flex items-center gap-1.5 text-[11px] text-[var(--primary)] bg-[var(--primary)]/10 px-2.5 py-0.5 rounded-full font-mono">
                    <MapPin className="w-3 h-3" />
                    <span>
                      {ngo.latitude.toFixed(4)}, {ngo.longitude.toFixed(4)}
                    </span>
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2.5 shrink-0 self-end md:self-center">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setRejectOrg(ngo);
                    setRejectReason('');
                  }}
                  className="text-xs h-9 px-3.5 text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10 border-[var(--color-danger)]/30"
                >
                  <XCircle className="w-4 h-4 mr-1.5" />
                  Reject
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => {
                    setApproveOrg(ngo);
                    setApproveNote('');
                  }}
                  className="text-xs h-9 px-4"
                >
                  <CheckCircle2 className="w-4 h-4 mr-1.5" />
                  Approve & Activate
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Approve Single Modal with Note */}
      {approveOrg && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150"
        >
          <div className="w-full max-w-md rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-emerald-500/10 text-emerald-500 flex items-center justify-center">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-[var(--text)]">Verify {approveOrg.name}</h3>
                <p className="text-xs text-[var(--muted)]">Grant relief access and notify organization</p>
              </div>
            </div>

            <p className="text-xs text-[var(--text)]">
              This will mark <span className="font-semibold">{approveOrg.name}</span> as an authorized NGO relief partner. They will immediately gain access to browse the Food Feed and claim surplus batches.
            </p>

            <div>
              <label className="text-xs font-semibold text-[var(--text)] block mb-1">
                Verification Note (Optional)
              </label>
              <textarea
                value={approveNote}
                onChange={(e) => setApproveNote(e.target.value)}
                placeholder="e.g., 80G tax exemption and trust deed verified via national registry."
                rows={2}
                className="w-full text-xs rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setApproveOrg(null)}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                disabled={verifyOrgMutation.isPending}
                onClick={handleApprove}
              >
                {verifyOrgMutation.isPending ? 'Verifying...' : 'Authorize NGO'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Reject Single Modal with Mandatory Reason */}
      {rejectOrg && (
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
                <h3 className="text-sm font-bold text-[var(--text)]">Reject {rejectOrg.name}</h3>
                <p className="text-xs text-[var(--muted)]">Mandatory audit and notification rationale</p>
              </div>
            </div>

            <p className="text-xs text-[var(--text)]">
              Rejecting will mark the organization as rejected and send an automated email notification explaining the rejection rationale.
            </p>

            <div>
              <label className="text-xs font-semibold text-[var(--text)] block mb-1">
                Rejection Reason (Required)
              </label>
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="e.g., Provided certificate of incorporation is expired or address could not be verified."
                rows={3}
                className="w-full text-xs rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setRejectOrg(null)}
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

      {/* Bulk Approve Confirmation Dialog */}
      <ConfirmDialog
        isOpen={isBulkApproveOpen}
        title={`Bulk Approve ${pendingNGOs.length} NGOs`}
        description={`Are you sure you want to verify and activate all ${pendingNGOs.length} pending NGOs? Each organization will be granted claiming rights and notified via email.`}
        confirmLabel={isBulkProcessing ? 'Processing...' : 'Approve All'}
        variant="primary"
        isLoading={isBulkProcessing}
        onConfirm={handleBulkApprove}
        onCancel={() => setIsBulkApproveOpen(false)}
      />
    </div>
  );
};

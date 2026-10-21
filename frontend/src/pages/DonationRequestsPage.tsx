import React, { useState, useMemo } from 'react';
import {
  HeartHandshake,
  Search,
  Clock,
  CheckCircle2,
  XCircle,
  Truck,
  Eye,
  Calendar,
  Package,
  Phone,
  AlertTriangle,
  X,
} from 'lucide-react';
import { PageHeader } from '../components/ui/PageHeader';
import { Button } from '../components/ui/Button';
import { StatusBadge, type StatusVariant } from '../components/ui/StatusBadge';
import { EmptyState } from '../components/ui/EmptyState';
import { Skeleton } from '../components/ui/Skeleton';
import {
  useDonationRequests,
  useApproveDonationRequest,
  useRejectDonationRequest,
  useSetInTransitDonationRequest,
  useCollectDonationRequest,
  useConfirmReceiptDonationRequest,
  useReportNoShowDonationRequest,
  useCurrentUser,
} from '../hooks/useData';
import type {
  DonationRequest,
  DonationRequestStatus,
  DonationRequestFilterTab,
} from '../types';

interface DonationRequestsPageProps {
  onTriggerToast?: (msg: string) => void;
  onNavigate?: (path: string) => void;
}

export const DonationRequestsPage: React.FC<DonationRequestsPageProps> = ({
  onTriggerToast,
  onNavigate,
}) => {
  const { data: user } = useCurrentUser();
  const isBusiness = user?.organization?.type === 'BUSINESS';
  const orgName = user?.organization?.name || 'Organization';

  // State
  const [activeTab, setActiveTab] = useState<DonationRequestFilterTab>('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  // Modals state
  const [selectedRequest, setSelectedRequest] = useState<DonationRequest | null>(null);
  const [isApproveOpen, setIsApproveOpen] = useState(false);
  const [isRejectOpen, setIsRejectOpen] = useState(false);
  const [isViewPickupOpen, setIsViewPickupOpen] = useState(false);

  // Form states for modals
  const [scheduledPickupTime, setScheduledPickupTime] = useState('');
  const [rejectionReason, setRejectionReason] = useState('');
  const [pickupNotes, setPickupNotes] = useState('');

  // Queries & Mutations
  const { data: requests = [], isLoading } = useDonationRequests();
  const approveMutation = useApproveDonationRequest();
  const rejectMutation = useRejectDonationRequest();
  const inTransitMutation = useSetInTransitDonationRequest();
  const collectMutation = useCollectDonationRequest();
  const confirmReceiptMutation = useConfirmReceiptDonationRequest();
  const noShowMutation = useReportNoShowDonationRequest();

  // Tab counts
  const tabCounts = useMemo(() => {
    return {
      ALL: requests.length,
      PENDING_APPROVAL: requests.filter((r) => r.status === 'REQUESTED').length,
      SCHEDULED: requests.filter((r) => r.status === 'APPROVED' || r.status === 'SCHEDULED').length,
      IN_TRANSIT: requests.filter((r) => r.status === 'IN_TRANSIT').length,
      COMPLETED: requests.filter((r) => r.status === 'COLLECTED' || r.status === 'COMPLETED').length,
    };
  }, [requests]);

  // Filtered requests
  const filteredRequests = useMemo(() => {
    let list = requests;

    // Filter by Tab
    if (activeTab === 'PENDING_APPROVAL') {
      list = list.filter((r) => r.status === 'REQUESTED');
    } else if (activeTab === 'SCHEDULED') {
      list = list.filter((r) => r.status === 'APPROVED' || r.status === 'SCHEDULED');
    } else if (activeTab === 'IN_TRANSIT') {
      list = list.filter((r) => r.status === 'IN_TRANSIT');
    } else if (activeTab === 'COMPLETED') {
      list = list.filter((r) => r.status === 'COLLECTED' || r.status === 'COMPLETED');
    }

    // Filter by Search Query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (r) =>
          r.request_code.toLowerCase().includes(q) ||
          r.item_name.toLowerCase().includes(q) ||
          r.recipient_name.toLowerCase().includes(q) ||
          r.donor_name.toLowerCase().includes(q) ||
          (r.driver_name && r.driver_name.toLowerCase().includes(q))
      );
    }

    return list;
  }, [requests, activeTab, searchQuery]);

  // Status Badge Mapper
  const getStatusBadge = (status: DonationRequestStatus) => {
    const map: Record<DonationRequestStatus, { label: string; variant: StatusVariant }> = {
      REQUESTED: { label: 'Pending Approval', variant: 'warning' },
      APPROVED: { label: 'Approved', variant: 'info' },
      SCHEDULED: { label: 'Scheduled', variant: 'info' },
      IN_TRANSIT: { label: 'In Transit', variant: 'info' },
      COLLECTED: { label: 'Collected', variant: 'success' },
      COMPLETED: { label: 'Completed', variant: 'success' },
      REJECTED: { label: 'Rejected', variant: 'danger' },
      CANCELLED: { label: 'Cancelled', variant: 'neutral' },
      NO_SHOW: { label: 'No Show', variant: 'danger' },
    };

    const config = map[status] || { label: status, variant: 'neutral' };
    return (
      <StatusBadge variant={config.variant} size="sm" dot>
        {config.label}
      </StatusBadge>
    );
  };

function getInitialApproveTime(requestedPickupTime?: string): string {
  if (requestedPickupTime) {
    return new Date(requestedPickupTime).toISOString().slice(0, 16);
  }
  const d = new Date();
  d.setHours(d.getHours() + 2);
  return d.toISOString().slice(0, 16);
}

  // Actions Handlers
  const handleOpenApprove = (req: DonationRequest) => {
    setSelectedRequest(req);
    setScheduledPickupTime(getInitialApproveTime(req.requested_pickup_time));
    setIsApproveOpen(true);
  };

  const handleConfirmApprove = async () => {
    if (!selectedRequest) return;
    try {
      await approveMutation.mutateAsync({
        codeOrId: selectedRequest.id,
        scheduledPickupTime: scheduledPickupTime ? new Date(scheduledPickupTime).toISOString() : undefined,
      });
      setIsApproveOpen(false);
      onTriggerToast?.(`Donation request ${selectedRequest.request_code} approved successfully!`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to approve donation request.';
      onTriggerToast?.(msg);
    }
  };

  const handleOpenReject = (req: DonationRequest) => {
    setSelectedRequest(req);
    setRejectionReason('');
    setIsRejectOpen(true);
  };

  const handleConfirmReject = async () => {
    if (!selectedRequest || !rejectionReason.trim()) return;
    try {
      await rejectMutation.mutateAsync({
        codeOrId: selectedRequest.id,
        reason: rejectionReason.trim(),
      });
      setIsRejectOpen(false);
      onTriggerToast?.(`Donation request ${selectedRequest.request_code} has been rejected.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to reject donation request.';
      onTriggerToast?.(msg);
    }
  };

  const handleOpenViewPickup = (req: DonationRequest) => {
    setSelectedRequest(req);
    setIsViewPickupOpen(true);
  };

  const handleMarkInTransit = async (req: DonationRequest) => {
    try {
      await inTransitMutation.mutateAsync({
        codeOrId: req.id,
        driver_name: req.driver_name || 'Designated Relief Driver',
        driver_phone: req.driver_phone || '+91 98765 43210',
        vehicle_plate: req.vehicle_plate || 'KA-01-AB-1234',
      });
      setIsViewPickupOpen(false);
      onTriggerToast?.(`Request ${req.request_code} marked as In Transit.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update transit status.';
      onTriggerToast?.(msg);
    }
  };

  const handleMarkCollected = async (req: DonationRequest) => {
    try {
      await collectMutation.mutateAsync({
        codeOrId: req.id,
        notes: pickupNotes.trim() || undefined,
      });
      setIsViewPickupOpen(false);
      onTriggerToast?.(`Request ${req.request_code} confirmed as Collected.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to record collection.';
      onTriggerToast?.(msg);
    }
  };

  const handleMarkCompleted = async (req: DonationRequest) => {
    try {
      await confirmReceiptMutation.mutateAsync({
        codeOrId: req.id,
        notes: pickupNotes.trim() || undefined,
      });
      setIsViewPickupOpen(false);
      onTriggerToast?.(`Request ${req.request_code} marked as Completed & Received!`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to complete receipt.';
      onTriggerToast?.(msg);
    }
  };

  const handleReportNoShow = async (req: DonationRequest) => {
    try {
      await noShowMutation.mutateAsync({
        codeOrId: req.id,
        notes: 'Vehicle or donor dispatch did not materialize in designated window.',
      });
      setIsViewPickupOpen(false);
      onTriggerToast?.(`Request ${req.request_code} marked as No Show.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to report no-show.';
      onTriggerToast?.(msg);
    }
  };

  return (
    <div id="donation-requests-page" className="space-y-6 pb-12 animate-in fade-in duration-200">
      {/* Page Header */}
      <PageHeader
        title="Donation Requests"
        subtitle={
          isBusiness
            ? `Review and manage food rescue and redistribution requests for ${orgName}.`
            : `Track your relief claims and scheduled pickups with donor partners.`
        }
        action={
          <div className="flex items-center gap-2">
            {onNavigate && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onNavigate('marketplace')}
                className="gap-1.5"
              >
                <Package className="w-4 h-4" />
                <span>Surplus Marketplace</span>
              </Button>
            )}
            {onNavigate && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onNavigate('schedule')}
                className="gap-1.5"
              >
                <Calendar className="w-4 h-4" />
                <span>Pickup Schedule</span>
              </Button>
            )}
          </div>
        }
      />

      {/* Filter Tabs & Search Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[var(--border)] pb-3">
        {/* Filter Tabs */}
        <div className="flex items-center gap-1 overflow-x-auto no-scrollbar py-1">
          {(
            [
              { key: 'ALL', label: 'All' },
              { key: 'PENDING_APPROVAL', label: 'Pending approval' },
              { key: 'SCHEDULED', label: 'Scheduled' },
              { key: 'IN_TRANSIT', label: 'In transit' },
              { key: 'COMPLETED', label: 'Completed' },
            ] as const
          ).map((tab) => {
            const count = tabCounts[tab.key];
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                id={`tab-${tab.key.toLowerCase()}`}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-[var(--primary)] text-[var(--primary-foreground)] shadow-xs'
                    : 'text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)]'
                }`}
              >
                <span>{tab.label}</span>
                <span
                  className={`px-1.5 py-0.2 rounded-full text-[10px] ${
                    isActive
                      ? 'bg-white/20 text-white'
                      : 'bg-[var(--surface-2)] text-[var(--muted)]'
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Search Input */}
        <div className="relative w-full md:w-72">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-[var(--muted)]" />
          <input
            id="donation-search-input"
            type="text"
            placeholder="Search by ID, item, NGO, donor..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 rounded-[8px] bg-[var(--surface)] border border-[var(--border)] text-xs text-[var(--text)] placeholder:text-[var(--muted)] focus:outline-hidden focus:ring-1 focus:ring-[var(--primary)]"
          />
        </div>
      </div>

      {/* Main Content Area */}
      {isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-14 w-full rounded-[10px]" />
          <Skeleton className="h-14 w-full rounded-[10px]" />
          <Skeleton className="h-14 w-full rounded-[10px]" />
        </div>
      ) : filteredRequests.length === 0 ? (
        <EmptyState
          icon={HeartHandshake}
          title="No donation requests found"
          description={
            searchQuery
              ? `No requests matching "${searchQuery}" in this view.`
              : 'There are currently no donation requests in this category.'
          }
          action={
            searchQuery ? (
              <Button variant="outline" size="sm" onClick={() => setSearchQuery('')}>
                Clear Search
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-[var(--text)]">
              <thead className="bg-[var(--surface-2)] border-b border-[var(--border)] text-[var(--muted)] uppercase font-semibold text-[11px] tracking-wider">
                <tr>
                  <th className="py-3 px-4">Request ID</th>
                  <th className="py-3 px-4">Item & Quantity</th>
                  <th className="py-3 px-4">{isBusiness ? 'NGO Partner' : 'Donor Business'}</th>
                  <th className="py-3 px-4">Pickup Time</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {filteredRequests.map((req) => {
                  const pickupTimeStr = req.scheduled_pickup_time || req.requested_pickup_time;
                  const dateFormatted = pickupTimeStr
                    ? new Date(pickupTimeStr).toLocaleString('en-IN', {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })
                    : 'Pending Confirmation';

                  return (
                    <tr
                      key={req.id}
                      id={`request-row-${req.id}`}
                      className="hover:bg-[var(--surface-2)]/50 transition-colors"
                    >
                      {/* Request ID */}
                      <td className="py-3.5 px-4 font-mono font-medium text-[var(--primary)] whitespace-nowrap">
                        {req.request_code}
                      </td>

                      {/* Item & Requested Quantity */}
                      <td className="py-3.5 px-4">
                        <div className="font-semibold text-[var(--text)] line-clamp-1">{req.item_name}</div>
                        <div className="text-[11px] text-[var(--muted)] flex items-center gap-1.5 mt-0.5">
                          <span className="font-medium text-[var(--text)]">
                            {req.requested_quantity} {req.unit}
                          </span>
                          {req.listing_title && req.listing_title !== req.item_name && (
                            <>
                              <span>•</span>
                              <span className="line-clamp-1">{req.listing_title}</span>
                            </>
                          )}
                        </div>
                      </td>

                      {/* NGO or Donor Partner */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <div className="w-7 h-7 rounded-full bg-[var(--surface-2)] flex items-center justify-center text-[var(--muted)] font-semibold text-[11px]">
                            {(isBusiness ? req.recipient_name : req.donor_name)?.slice(0, 2).toUpperCase()}
                          </div>
                          <div>
                            <div className="font-medium text-[var(--text)]">
                              {isBusiness ? req.recipient_name : req.donor_name}
                            </div>
                            <div className="text-[11px] text-[var(--muted)]">
                              {isBusiness ? req.recipient_contact_phone : req.donor_address}
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* Pickup Time Window */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <div className="flex items-center gap-1.5 text-xs text-[var(--text)] font-medium">
                          <Clock className="w-3.5 h-3.5 text-[var(--muted)]" />
                          <span>{dateFormatted}</span>
                        </div>
                        {req.scheduled_pickup_time && (
                          <span className="text-[10px] text-[var(--color-success)] font-medium mt-0.5 block">
                            Confirmed Window
                          </span>
                        )}
                      </td>

                      {/* Status Badges */}
                      <td className="py-3.5 px-4 whitespace-nowrap">{getStatusBadge(req.status)}</td>

                      {/* Actions */}
                      <td className="py-3.5 px-4 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1.5">
                          {/* Approve Action (Only when Pending Approval / REQUESTED) */}
                          {req.status === 'REQUESTED' && isBusiness && (
                            <Button
                              id={`approve-btn-${req.id}`}
                              variant="primary"
                              size="sm"
                              onClick={() => handleOpenApprove(req)}
                              className="text-[11px] py-1 px-2.5 h-auto bg-[var(--color-success)] hover:bg-[var(--color-success)]/90 text-white"
                            >
                              <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                              Approve
                            </Button>
                          )}

                          {/* Reject Action (Only when Pending Approval / REQUESTED) */}
                          {req.status === 'REQUESTED' && isBusiness && (
                            <Button
                              id={`reject-btn-${req.id}`}
                              variant="outline"
                              size="sm"
                              onClick={() => handleOpenReject(req)}
                              className="text-[11px] py-1 px-2.5 h-auto text-[var(--color-danger)] hover:bg-[var(--color-danger-subtle)] border-[var(--color-danger-border)]"
                            >
                              <XCircle className="w-3.5 h-3.5 mr-1" />
                              Reject
                            </Button>
                          )}

                          {/* View Pickup Action */}
                          <Button
                            id={`view-pickup-btn-${req.id}`}
                            variant="outline"
                            size="sm"
                            onClick={() => handleOpenViewPickup(req)}
                            className="text-[11px] py-1 px-2.5 h-auto gap-1"
                          >
                            <Eye className="w-3.5 h-3.5" />
                            View Pickup
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* APPROVE MODAL */}
      {isApproveOpen && selectedRequest && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-[14px] p-6 max-w-md w-full shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-[var(--color-success)]" />
                <h3 className="text-sm font-bold text-[var(--text)]">Approve Donation Request</h3>
              </div>
              <button
                onClick={() => setIsApproveOpen(false)}
                className="text-[var(--muted)] hover:text-[var(--text)]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="p-3 bg-[var(--surface-2)] rounded-[8px] space-y-1">
                <div className="font-semibold text-[var(--text)]">{selectedRequest.item_name}</div>
                <div className="text-[var(--muted)]">
                  Requested by <span className="font-medium text-[var(--text)]">{selectedRequest.recipient_name}</span>
                </div>
                <div className="text-[var(--muted)]">
                  Quantity: <span className="font-medium text-[var(--text)]">{selectedRequest.requested_quantity} {selectedRequest.unit}</span>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="font-semibold text-[var(--text)]">Confirmed Pickup Window Time</label>
                <input
                  type="datetime-local"
                  value={scheduledPickupTime}
                  onChange={(e) => setScheduledPickupTime(e.target.value)}
                  className="w-full px-3 py-2 rounded-[8px] border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)] focus:ring-1 focus:ring-[var(--primary)]"
                />
                <p className="text-[11px] text-[var(--muted)]">
                  The recipient NGO will be notified to dispatch their verified driver to your loading dock.
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-[var(--border)]">
              <Button variant="outline" size="sm" onClick={() => setIsApproveOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleConfirmApprove}
                disabled={approveMutation.isPending}
                className="bg-[var(--color-success)] hover:bg-[var(--color-success)]/90 text-white"
              >
                {approveMutation.isPending ? 'Approving...' : 'Confirm Approval'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* REJECT MODAL */}
      {isRejectOpen && selectedRequest && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-[14px] p-6 max-w-md w-full shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
              <div className="flex items-center gap-2">
                <XCircle className="w-5 h-5 text-[var(--color-danger)]" />
                <h3 className="text-sm font-bold text-[var(--text)]">Reject Donation Request</h3>
              </div>
              <button
                onClick={() => setIsRejectOpen(false)}
                className="text-[var(--muted)] hover:text-[var(--text)]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <p className="text-[var(--muted)]">
                Rejecting request <span className="font-mono font-medium text-[var(--text)]">{selectedRequest.request_code}</span> for {selectedRequest.requested_quantity} {selectedRequest.unit} of {selectedRequest.item_name}.
              </p>

              <div className="space-y-1.5">
                <label className="font-semibold text-[var(--text)]">
                  Reason for Rejection <span className="text-[var(--color-danger)]">*</span>
                </label>
                <textarea
                  rows={3}
                  placeholder="e.g. Storage capacity exceeded, batch already dispatched, cold chain requirement mismatch..."
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  className="w-full px-3 py-2 rounded-[8px] border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)] placeholder:text-[var(--muted)] focus:ring-1 focus:ring-[var(--primary)]"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-[var(--border)]">
              <Button variant="outline" size="sm" onClick={() => setIsRejectOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleConfirmReject}
                disabled={rejectMutation.isPending || !rejectionReason.trim()}
                className="bg-[var(--color-danger)] hover:bg-[var(--color-danger)]/90 text-white"
              >
                {rejectMutation.isPending ? 'Rejecting...' : 'Confirm Rejection'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* VIEW PICKUP MODAL */}
      {isViewPickupOpen && selectedRequest && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-[14px] p-6 max-w-lg w-full shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <Truck className="w-5 h-5 text-[var(--primary)]" />
                  <h3 className="text-base font-bold text-[var(--text)]">Pickup Details & Status Flow</h3>
                </div>
                <div className="font-mono text-xs text-[var(--muted)]">{selectedRequest.request_code}</div>
              </div>
              <button
                onClick={() => setIsViewPickupOpen(false)}
                className="text-[var(--muted)] hover:text-[var(--text)]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Status Tracker */}
            <div className="p-3 bg-[var(--surface-2)] rounded-[10px] space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-[var(--muted)]">Lifecycle Status:</span>
                {getStatusBadge(selectedRequest.status)}
              </div>
              {/* Status progression bar */}
              <div className="grid grid-cols-5 gap-1 pt-1 text-[10px] text-center font-medium">
                {[
                  { key: 'REQUESTED', label: 'Requested' },
                  { key: 'APPROVED', label: 'Approved' },
                  { key: 'SCHEDULED', label: 'Scheduled' },
                  { key: 'IN_TRANSIT', label: 'In Transit' },
                  { key: 'COMPLETED', label: 'Completed' },
                ].map((step) => {
                  const isCurrent = selectedRequest.status === step.key;
                  return (
                    <div
                      key={step.key}
                      className={`py-1 rounded-[6px] border ${
                        isCurrent
                          ? 'bg-[var(--primary)] text-white border-[var(--primary)]'
                          : 'bg-[var(--surface)] text-[var(--muted)] border-[var(--border)]'
                      }`}
                    >
                      {step.label}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Item and Partner Summary */}
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="p-3 border border-[var(--border)] rounded-[8px] space-y-1">
                <span className="text-[11px] text-[var(--muted)] uppercase font-semibold">Food Item</span>
                <div className="font-bold text-[var(--text)]">{selectedRequest.item_name}</div>
                <div className="text-[var(--primary)] font-medium">
                  {selectedRequest.requested_quantity} {selectedRequest.unit}
                </div>
              </div>

              <div className="p-3 border border-[var(--border)] rounded-[8px] space-y-1">
                <span className="text-[11px] text-[var(--muted)] uppercase font-semibold">
                  {isBusiness ? 'Recipient NGO' : 'Donor Business'}
                </span>
                <div className="font-bold text-[var(--text)]">
                  {isBusiness ? selectedRequest.recipient_name : selectedRequest.donor_name}
                </div>
                <div className="text-[var(--muted)] flex items-center gap-1">
                  <Phone className="w-3 h-3" />
                  <span>{isBusiness ? selectedRequest.recipient_contact_phone : selectedRequest.donor_phone}</span>
                </div>
              </div>
            </div>

            {/* Logistics & Driver Details */}
            <div className="p-3 border border-[var(--border)] rounded-[8px] space-y-2 text-xs">
              <div className="font-semibold text-[var(--text)] flex items-center gap-1.5">
                <Truck className="w-4 h-4 text-[var(--primary)]" />
                <span>Logistics & Transport Handoff</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div>
                  <span className="text-[var(--muted)] block">Assigned Driver:</span>
                  <span className="font-medium text-[var(--text)]">
                    {selectedRequest.driver_name || 'Driver to be dispatched'}
                  </span>
                </div>
                <div>
                  <span className="text-[var(--muted)] block">Vehicle Registration:</span>
                  <span className="font-medium text-[var(--text)]">
                    {selectedRequest.vehicle_plate || 'KA-01-AB-1234'}
                  </span>
                </div>
                <div>
                  <span className="text-[var(--muted)] block">Scheduled Window:</span>
                  <span className="font-medium text-[var(--text)]">
                    {selectedRequest.scheduled_pickup_time
                      ? new Date(selectedRequest.scheduled_pickup_time).toLocaleString('en-IN')
                      : 'Pending Approval'}
                  </span>
                </div>
                <div>
                  <span className="text-[var(--muted)] block">Facility Location:</span>
                  <span className="font-medium text-[var(--text)] line-clamp-1">
                    {selectedRequest.donor_address}
                  </span>
                </div>
              </div>

              {selectedRequest.pickup_notes && (
                <div className="pt-1.5 border-t border-[var(--border)] text-[11px] text-[var(--muted)]">
                  <span className="font-medium text-[var(--text)]">Notes: </span>
                  {selectedRequest.pickup_notes}
                </div>
              )}
            </div>

            {/* Optional Handoff Notes */}
            <div className="space-y-1.5 pt-2 border-t border-[var(--border)]">
              <label className="text-xs font-semibold text-[var(--text)]">
                Chain-of-Custody & Inspection Notes (Optional)
              </label>
              <input
                type="text"
                value={pickupNotes}
                onChange={(e) => setPickupNotes(e.target.value)}
                placeholder="e.g. Temperature checked at loading dock, cold chain intact."
                className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-1.5 text-xs text-[var(--text)] focus:outline-none focus:border-[var(--primary)]"
              />
            </div>

            {/* Lifecycle Progression Action Triggers */}
            <div className="space-y-2 pt-2 border-t border-[var(--border)]">
              <span className="text-xs font-semibold text-[var(--text)] block">Advance Lifecycle State:</span>
              <div className="flex flex-wrap gap-2">
                {/* Advance to IN TRANSIT */}
                {(selectedRequest.status === 'APPROVED' || selectedRequest.status === 'SCHEDULED') && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleMarkInTransit(selectedRequest)}
                    className="text-xs gap-1.5"
                  >
                    <Truck className="w-3.5 h-3.5" />
                    Dispatch Driver (In Transit)
                  </Button>
                )}

                {/* Advance to COLLECTED */}
                {(selectedRequest.status === 'SCHEDULED' || selectedRequest.status === 'IN_TRANSIT') && (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => handleMarkCollected(selectedRequest)}
                    className="text-xs gap-1.5 bg-[var(--color-success)] hover:bg-[var(--color-success)]/90 text-white"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Confirm Collection Handover
                  </Button>
                )}

                {/* Advance to COMPLETED */}
                {selectedRequest.status === 'COLLECTED' && (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => handleMarkCompleted(selectedRequest)}
                    className="text-xs gap-1.5 bg-[var(--primary)] text-white"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Confirm Relief Receipt
                  </Button>
                )}

                {/* Report No Show */}
                {(selectedRequest.status === 'SCHEDULED' || selectedRequest.status === 'IN_TRANSIT') && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleReportNoShow(selectedRequest)}
                    className="text-xs text-[var(--color-danger)] hover:bg-[var(--color-danger-subtle)]"
                  >
                    <AlertTriangle className="w-3.5 h-3.5 mr-1" />
                    Report No Show
                  </Button>
                )}
              </div>
            </div>

            {/* Footer */}
            <div className="flex justify-end pt-2 border-t border-[var(--border)]">
              <Button variant="outline" size="sm" onClick={() => setIsViewPickupOpen(false)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

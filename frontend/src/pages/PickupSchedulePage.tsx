import React, { useState, useMemo } from 'react';
import {
  Calendar,
  Clock,
  Truck,
  CheckCircle2,
  AlertTriangle,
  MapPin,
  Phone,
  User,
  ShieldCheck,
  Search,
  Building2,
  X,
} from 'lucide-react';
import { PageHeader } from '../components/ui/PageHeader';
import { Button } from '../components/ui/Button';
import { StatusBadge, type StatusVariant } from '../components/ui/StatusBadge';
import { EmptyState } from '../components/ui/EmptyState';
import { Skeleton } from '../components/ui/Skeleton';
import {
  usePickupSchedule,
  useSetInTransitDonationRequest,
  useCollectDonationRequest,
  useConfirmReceiptDonationRequest,
  useReportNoShowDonationRequest,
} from '../hooks/useData';
import type {
  PickupScheduleItem,
  DonationRequestStatus,
} from '../types';
import { dataSource } from '../services';

interface PickupSchedulePageProps {
  onTriggerToast?: (msg: string) => void;
  onNavigate?: (path: string) => void;
}

type ScheduleTab = 'ALL' | 'TODAY' | 'TOMORROW' | 'UPCOMING' | 'OVERDUE' | 'COMPLETED';

export const PickupSchedulePage: React.FC<PickupSchedulePageProps> = ({
  onTriggerToast,
  onNavigate,
}) => {

  // State
  const [activeTab, setActiveTab] = useState<ScheduleTab>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [isExporting, setIsExporting] = useState(false);

  // Modals state
  const [dispatchItem, setDispatchItem] = useState<PickupScheduleItem | null>(null);
  const [driverName, setDriverName] = useState('');
  const [driverPhone, setDriverPhone] = useState('');
  const [vehiclePlate, setVehiclePlate] = useState('');

  const [collectItem, setCollectItem] = useState<PickupScheduleItem | null>(null);
  const [collectNotes, setCollectNotes] = useState('');

  // Queries & Mutations
  const { data: schedule = [], isLoading } = usePickupSchedule();
  const inTransitMutation = useSetInTransitDonationRequest();
  const collectMutation = useCollectDonationRequest();
  const confirmReceiptMutation = useConfirmReceiptDonationRequest();
  const noShowMutation = useReportNoShowDonationRequest();

  // Helper date categorization
  const now = new Date();
  const todayStr = now.toISOString().slice(0, 10);
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const tomorrowStr = tomorrow.toISOString().slice(0, 10);

  // Tab counts
  const tabCounts = useMemo(() => {
    return {
      ALL: schedule.length,
      TODAY: schedule.filter((i) => i.scheduled_pickup_time.startsWith(todayStr)).length,
      TOMORROW: schedule.filter((i) => i.scheduled_pickup_time.startsWith(tomorrowStr)).length,
      UPCOMING: schedule.filter((i) => ['APPROVED', 'SCHEDULED', 'IN_TRANSIT'].includes(i.status)).length,
      OVERDUE: schedule.filter((i) => i.is_overdue).length,
      COMPLETED: schedule.filter((i) => ['COLLECTED', 'COMPLETED'].includes(i.status)).length,
    };
  }, [schedule, todayStr, tomorrowStr]);

  // Filtered schedule
  const filteredSchedule = useMemo(() => {
    return schedule.filter((item) => {
      // Search
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesCode = item.request_code.toLowerCase().includes(q);
        const matchesItem = item.item_name.toLowerCase().includes(q);
        const matchesDonor = item.donor_name.toLowerCase().includes(q);
        const matchesRecipient = item.recipient_name.toLowerCase().includes(q);
        const matchesDriver = item.driver_name?.toLowerCase().includes(q);
        if (!matchesCode && !matchesItem && !matchesDonor && !matchesRecipient && !matchesDriver) {
          return false;
        }
      }

      // Tab filter
      if (activeTab === 'TODAY') {
        return item.scheduled_pickup_time.startsWith(todayStr);
      }
      if (activeTab === 'TOMORROW') {
        return item.scheduled_pickup_time.startsWith(tomorrowStr);
      }
      if (activeTab === 'UPCOMING') {
        return ['APPROVED', 'SCHEDULED', 'IN_TRANSIT'].includes(item.status);
      }
      if (activeTab === 'OVERDUE') {
        return item.is_overdue;
      }
      if (activeTab === 'COMPLETED') {
        return ['COLLECTED', 'COMPLETED'].includes(item.status);
      }

      return true;
    });
  }, [schedule, searchQuery, activeTab, todayStr, tomorrowStr]);

  // Calendar .ics export handler
  const handleExportIcs = async (requestId?: number) => {
    try {
      setIsExporting(true);
      const blob = await dataSource.exportScheduleIcs(requestId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = requestId ? `pickup_${requestId}.ics` : `pickup_schedule.ics`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      onTriggerToast?.(requestId ? 'Pickup event exported (.ics calendar).' : 'Pickup schedule exported (.ics calendar).');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to export calendar';
      onTriggerToast?.(msg);
    } finally {
      setIsExporting(false);
    }
  };

  // Dispatch driver submit
  const handleDispatchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!dispatchItem) return;

    inTransitMutation.mutate(
      {
        codeOrId: dispatchItem.request_code || dispatchItem.id,
        driver_name: driverName || 'Volunteer Driver',
        driver_phone: driverPhone || '+91 98765 43210',
        vehicle_plate: vehiclePlate || 'KA-01-XX-0000',
      },
      {
        onSuccess: () => {
          onTriggerToast?.(`Driver dispatched for ${dispatchItem.request_code}! Status changed to In Transit.`);
          setDispatchItem(null);
          setDriverName('');
          setDriverPhone('');
          setVehiclePlate('');
        },
        onError: (err: unknown) => {
          const msg = err instanceof Error ? err.message : 'Failed to dispatch driver';
          onTriggerToast?.(msg);
        },
      }
    );
  };

  // Collect submit
  const handleCollectSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!collectItem) return;

    collectMutation.mutate(
      {
        codeOrId: collectItem.request_code || collectItem.id,
        notes: collectNotes,
      },
      {
        onSuccess: () => {
          onTriggerToast?.(`Pickup recorded for ${collectItem.request_code}! Status: Collected.`);
          setCollectItem(null);
          setCollectNotes('');
        },
        onError: (err: unknown) => {
          const msg = err instanceof Error ? err.message : 'Failed to record pickup';
          onTriggerToast?.(msg);
        },
      }
    );
  };

  // Status badge config
  const getStatusBadge = (status: DonationRequestStatus): { variant: StatusVariant; label: string } => {
    switch (status) {
      case 'APPROVED':
      case 'SCHEDULED':
        return { variant: 'info', label: 'Scheduled' };
      case 'IN_TRANSIT':
        return { variant: 'warning', label: 'In Transit' };
      case 'COLLECTED':
        return { variant: 'neutral', label: 'Collected' };
      case 'COMPLETED':
        return { variant: 'success', label: 'Completed' };
      case 'NO_SHOW':
        return { variant: 'danger', label: 'No Show' };
      default:
        return { variant: 'neutral', label: status };
    }
  };

  // Countdown badge
  const renderCountdownPill = (item: PickupScheduleItem) => {
    if (item.status === 'COMPLETED' || item.status === 'COLLECTED') {
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-[var(--color-success)] bg-[var(--color-success-subtle)] px-2 py-0.5 rounded-[4px] border border-[var(--color-success-border)]">
          <CheckCircle2 className="w-3 h-3" />
          Handoff Complete
        </span>
      );
    }

    if (item.is_overdue) {
      const elapsed = item.overdue_minutes
        ? `${Math.floor(item.overdue_minutes / 60)}h ${item.overdue_minutes % 60}m`
        : '';
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-bold text-rose-600 dark:text-rose-400 bg-rose-500/15 px-2.5 py-0.5 rounded-[4px] border border-rose-500/30 animate-pulse">
          <AlertTriangle className="w-3 h-3" />
          Overdue {elapsed ? `(${elapsed})` : ''}
        </span>
      );
    }

    if (item.countdown_minutes !== null && item.countdown_minutes !== undefined) {
      const mins = item.countdown_minutes;
      if (mins < 60) {
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-amber-500 bg-amber-500/10 px-2.5 py-0.5 rounded-[4px] border border-amber-500/20">
            <Clock className="w-3 h-3" />
            In {mins} mins
          </span>
        );
      }
      const hrs = Math.floor(mins / 60);
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[var(--muted)] bg-[var(--surface-2)] px-2 py-0.5 rounded-[4px] border border-[var(--border)]">
          <Clock className="w-3 h-3" />
          In {hrs}h {mins % 60}m
        </span>
      );
    }

    return null;
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-150">
      {/* Header */}
      <PageHeader
        title="Pickup & Logistics Schedule"
        subtitle="Coordinate timely volunteer arrival, driver dispatch, and secure chain-of-custody transfer."
        action={
          <div className="flex items-center gap-2 flex-wrap">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleExportIcs()}
              disabled={isExporting}
              className="text-xs font-semibold gap-1.5 border-[var(--primary)]/30 hover:border-[var(--primary)] text-[var(--primary)]"
              title="Export schedule as RFC 5545 .ics calendar"
            >
              <Calendar className="w-3.5 h-3.5" />
              <span>{isExporting ? 'Exporting...' : 'Export Calendar (.ics)'}</span>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onNavigate?.('donations')}
              className="text-xs"
            >
              Donation Requests
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onNavigate?.('marketplace')}
              className="text-xs"
            >
              Surplus Marketplace
            </Button>
          </div>
        }
      />

      {/* Filter Tabs & Search Bar */}
      <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-4 shadow-2xs space-y-3.5">
        <div className="flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
          {/* Tabs */}
          <div className="flex items-center gap-1 overflow-x-auto pb-1 md:pb-0 no-scrollbar">
            {[
              { id: 'ALL', label: 'All Pickups', count: tabCounts.ALL },
              { id: 'TODAY', label: "Today's Agenda", count: tabCounts.TODAY },
              { id: 'TOMORROW', label: 'Tomorrow', count: tabCounts.TOMORROW },
              { id: 'UPCOMING', label: 'Active Transit', count: tabCounts.UPCOMING },
              { id: 'OVERDUE', label: 'Overdue Pickups', count: tabCounts.OVERDUE, isDanger: tabCounts.OVERDUE > 0 },
              { id: 'COMPLETED', label: 'Completed', count: tabCounts.COMPLETED },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id as ScheduleTab)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                  activeTab === tab.id
                    ? 'bg-[var(--primary)] text-[var(--primary-foreground)] shadow-2xs'
                    : tab.isDanger
                    ? 'bg-rose-500/15 text-rose-600 dark:text-rose-400 hover:bg-rose-500/25'
                    : 'bg-[var(--surface-2)] text-[var(--muted)] hover:text-[var(--text)]'
                }`}
              >
                <span>{tab.label}</span>
                <span className={`px-1.5 py-0.2 rounded-full text-[10px] tabular-nums ${
                  tab.isDanger ? 'bg-rose-500/30 text-rose-700 dark:text-rose-300 font-bold' : 'bg-black/10 dark:bg-white/10'
                }`}>
                  {tab.count}
                </span>
              </button>
            ))}
          </div>

          {/* Search */}
          <div className="relative w-full md:w-64 shrink-0">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--muted)]" />
            <input
              type="text"
              placeholder="Search request, driver, NGO..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] pl-8.5 pr-4 py-1.5 text-xs text-[var(--text)] placeholder-[var(--muted)] focus:outline-none focus:border-[var(--primary)]"
            />
          </div>
        </div>
      </div>

      {/* Main Schedule List */}
      {isLoading ? (
        <div className="space-y-3">
          <Skeleton variant="card" />
          <Skeleton variant="card" />
        </div>
      ) : filteredSchedule.length === 0 ? (
        <EmptyState
          icon={Truck}
          title="No scheduled pickups found"
          description="Approved donation requests with confirmed pickup times will automatically appear in this logistics timeline."
          action={
            <Button variant="outline" size="sm" onClick={() => onNavigate?.('donations')}>
              View Donation Requests
            </Button>
          }
        />
      ) : (
        <div className="space-y-3">
          {filteredSchedule.map((item) => {
            const badge = getStatusBadge(item.status);
            const canDispatch = item.status === 'SCHEDULED' || item.status === 'APPROVED';
            const canCollect = item.status === 'IN_TRANSIT';
            const canComplete = item.status === 'COLLECTED';

            return (
              <div
                key={item.id}
                className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-4 shadow-2xs hover:border-[var(--primary)]/30 transition-all space-y-3"
              >
                {/* Top Row: Request Code, Item, Status, Countdown */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[var(--border)] pb-3">
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <span className="font-mono text-xs font-bold text-[var(--primary)] bg-[var(--primary)]/10 px-2 py-0.5 rounded-[4px]">
                      {item.request_code}
                    </span>
                    <span className="text-sm font-bold text-[var(--text)]">
                      {item.item_name}
                    </span>
                    <span className="text-xs font-semibold text-[var(--muted)] tabular-nums">
                      • {item.quantity} {item.unit}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {renderCountdownPill(item)}
                    <StatusBadge variant={badge.variant}>{badge.label}</StatusBadge>
                  </div>
                </div>

                {/* Overdue alert banner if applicable */}
                {item.is_overdue && (
                  <div className="flex items-center gap-2 px-3 py-2 rounded-[8px] bg-rose-500/10 border border-rose-500/25 text-rose-600 dark:text-rose-400 text-xs font-medium">
                    <AlertTriangle className="w-4 h-4 shrink-0 text-rose-500" />
                    <span>
                      Pickup window has passed{item.overdue_minutes ? ` (${Math.floor(item.overdue_minutes / 60)}h ${item.overdue_minutes % 60}m ago)` : ''}. Please dispatch driver, complete handoff, or report no-show.
                    </span>
                  </div>
                )}

                {/* Middle Grid: Logistics & Partner Details */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                  {/* Scheduled Window */}
                  <div className="rounded-[8px] bg-[var(--surface-2)]/60 p-3 border border-[var(--border)] space-y-1">
                    <div className="flex items-center gap-1.5 text-[var(--muted)] font-medium">
                      <Calendar className="w-3.5 h-3.5 text-[var(--primary)]" />
                      <span>Pickup Time Window</span>
                    </div>
                    <p className="font-bold text-[var(--text)] text-xs pt-0.5 tabular-nums">
                      {new Date(item.scheduled_pickup_time).toLocaleDateString([], {
                        weekday: 'short',
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                      })}
                    </p>
                    <p className="text-[11px] text-[var(--primary)] font-semibold tabular-nums">
                      {new Date(item.scheduled_pickup_time).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </p>
                  </div>

                  {/* Donor Facility */}
                  <div className="rounded-[8px] bg-[var(--surface-2)]/60 p-3 border border-[var(--border)] space-y-1">
                    <div className="flex items-center gap-1.5 text-[var(--muted)] font-medium">
                      <Building2 className="w-3.5 h-3.5 text-[var(--primary)]" />
                      <span>Donor Facility (Pickup Origin)</span>
                    </div>
                    <p className="font-bold text-[var(--text)] truncate">{item.donor_name}</p>
                    <div className="flex items-center gap-1 text-[11px] text-[var(--muted)] truncate">
                      <MapPin className="w-3 h-3 shrink-0" />
                      <span className="truncate">{item.donor_address || 'Loading Dock 2'}</span>
                    </div>
                    {item.donor_phone && (
                      <div className="flex items-center gap-1 text-[11px] text-[var(--muted)]">
                        <Phone className="w-3 h-3 shrink-0" />
                        <span>{item.donor_phone}</span>
                      </div>
                    )}
                  </div>

                  {/* Recipient NGO & Driver */}
                  <div className="rounded-[8px] bg-[var(--surface-2)]/60 p-3 border border-[var(--border)] space-y-1">
                    <div className="flex items-center gap-1.5 text-[var(--muted)] font-medium">
                      <Truck className="w-3.5 h-3.5 text-[var(--primary)]" />
                      <span>Rescue Vehicle & Driver</span>
                    </div>
                    <p className="font-bold text-[var(--text)] truncate">
                      {item.recipient_name}
                    </p>
                    {item.driver_name ? (
                      <div className="text-[11px] text-[var(--text)] font-medium space-y-0.5">
                        <div className="flex items-center gap-1">
                          <User className="w-3 h-3 text-[var(--muted)] shrink-0" />
                          <span>{item.driver_name}</span>
                          {item.vehicle_plate && (
                            <span className="text-[var(--muted)] font-mono">({item.vehicle_plate})</span>
                          )}
                        </div>
                        {item.driver_phone && (
                          <div className="flex items-center gap-1 text-[var(--muted)]">
                            <Phone className="w-3 h-3 shrink-0" />
                            <span>{item.driver_phone}</span>
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="text-[11px] text-[var(--muted)] italic">
                        No driver assigned yet
                      </p>
                    )}
                  </div>
                </div>

                {/* Bottom Row Actions */}
                <div className="flex items-center justify-between pt-2">
                  <div className="text-[11px] text-[var(--muted)]">
                    Chain of custody tracked with tamper-evident audit logs.
                  </div>

                  <div className="flex items-center gap-2">
                    {canDispatch && (
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => {
                          setDispatchItem(item);
                          setDriverName(item.driver_name || '');
                          setDriverPhone(item.driver_phone || '');
                          setVehiclePlate(item.vehicle_plate || '');
                        }}
                        className="text-xs font-semibold"
                      >
                        <Truck className="w-3.5 h-3.5" />
                        <span>Dispatch Driver (In Transit)</span>
                      </Button>
                    )}

                    {canCollect && (
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => {
                          setCollectItem(item);
                          setCollectNotes('');
                        }}
                        className="text-xs font-semibold"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Confirm Handoff (Collected)</span>
                      </Button>
                    )}

                    {canComplete && (
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => {
                          confirmReceiptMutation.mutate(
                            { codeOrId: item.request_code || item.id },
                            {
                              onSuccess: () => {
                                onTriggerToast?.(`Receipt verified for ${item.request_code}! Lifecycle completed.`);
                              },
                            }
                          );
                        }}
                        disabled={confirmReceiptMutation.isPending}
                        className="text-xs font-semibold"
                      >
                        <ShieldCheck className="w-3.5 h-3.5" />
                        <span>Verify Final Receipt (Complete)</span>
                      </Button>
                    )}

                    {!['COLLECTED', 'COMPLETED', 'NO_SHOW'].includes(item.status) && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          if (confirm(`Report no-show for ${item.request_code}?`)) {
                            noShowMutation.mutate(
                              { codeOrId: item.request_code || item.id, notes: 'Vehicle failed to arrive' },
                              {
                                onSuccess: () => onTriggerToast?.('No-show reported'),
                              }
                            );
                          }
                        }}
                        className="text-xs text-[var(--color-danger)] hover:bg-[var(--color-danger-subtle)]"
                      >
                        Report No-Show
                      </Button>
                    )}

                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleExportIcs(item.id)}
                      className="text-xs font-medium gap-1 text-[var(--muted)] hover:text-[var(--text)]"
                      title="Download .ics calendar event for this pickup"
                    >
                      <Calendar className="w-3.5 h-3.5 text-[var(--primary)]" />
                      <span>Add to Calendar (.ics)</span>
                    </Button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* MODAL 1: Dispatch Driver */}
      {dispatchItem && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in"
        >
          <div className="w-full max-w-md rounded-[16px] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl space-y-5 animate-in zoom-in-95 duration-150">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-base font-bold text-[var(--text)]">Dispatch Transport Driver</h3>
                <p className="text-xs text-[var(--muted)] mt-0.5">
                  Update {dispatchItem.request_code} to In Transit with vehicle details.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setDispatchItem(null)}
                className="p-1 rounded-[6px] text-[var(--muted)] hover:text-[var(--text)]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleDispatchSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-[var(--text)]">
                  Driver Full Name *
                </label>
                <input
                  type="text"
                  required
                  value={driverName}
                  onChange={(e) => setDriverName(e.target.value)}
                  placeholder="e.g. Anand Kumar"
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--text)] focus:outline-none focus:border-[var(--primary)]"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-[var(--text)]">
                  Driver Contact Phone *
                </label>
                <input
                  type="tel"
                  required
                  value={driverPhone}
                  onChange={(e) => setDriverPhone(e.target.value)}
                  placeholder="e.g. +91 98765 43210"
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--text)] focus:outline-none focus:border-[var(--primary)]"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-[var(--text)]">
                  Vehicle License Plate *
                </label>
                <input
                  type="text"
                  required
                  value={vehiclePlate}
                  onChange={(e) => setVehiclePlate(e.target.value)}
                  placeholder="e.g. KA-03-MG-4819"
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--text)] focus:outline-none focus:border-[var(--primary)] uppercase"
                />
              </div>

              <div className="pt-2 flex items-center justify-end gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  type="button"
                  onClick={() => setDispatchItem(null)}
                >
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  type="submit"
                  disabled={inTransitMutation.isPending}
                >
                  {inTransitMutation.isPending ? 'Updating...' : 'Confirm Driver Dispatch'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: Confirm Collection */}
      {collectItem && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in"
        >
          <div className="w-full max-w-md rounded-[16px] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl space-y-5 animate-in zoom-in-95 duration-150">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-base font-bold text-[var(--text)]">Confirm Food Handoff</h3>
                <p className="text-xs text-[var(--muted)] mt-0.5">
                  Confirm physical collection of {collectItem.quantity} {collectItem.unit} of {collectItem.item_name}.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setCollectItem(null)}
                className="p-1 rounded-[6px] text-[var(--muted)] hover:text-[var(--text)]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCollectSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-[var(--text)]">
                  Inspection Notes & Temperature at Handoff
                </label>
                <textarea
                  rows={3}
                  value={collectNotes}
                  onChange={(e) => setCollectNotes(e.target.value)}
                  placeholder="e.g. All sealed cartons received in clean condition. Chilled temperature verified at 3.2°C."
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--text)] focus:outline-none focus:border-[var(--primary)] resize-none"
                />
              </div>

              <div className="pt-2 flex items-center justify-end gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  type="button"
                  onClick={() => setCollectItem(null)}
                >
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  type="submit"
                  disabled={collectMutation.isPending}
                >
                  {collectMutation.isPending ? 'Recording...' : 'Confirm Handoff (Collected)'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

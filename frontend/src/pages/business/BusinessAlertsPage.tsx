import React, { useState, useMemo } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Filter,
  CheckCheck,
  Clock,
  ShieldAlert,
  Info,
  RefreshCw,
  Search,
} from 'lucide-react';
import { Button } from '../../components/ui/Button';
import { PageHeader } from '../../components/ui/PageHeader';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import {
  useAlerts,
  useAcknowledgeAlert,
  useBulkAcknowledgeAlerts,
} from '../../hooks/useData';
import type { Alert } from '../../types';

interface BusinessAlertsPageProps {
  onTriggerToast: (msg: string) => void;
  onNavigate?: (path: string) => void;
}

export const BusinessAlertsPage: React.FC<BusinessAlertsPageProps> = ({
  onTriggerToast,
  onNavigate: _onNavigate,
}) => {
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');
  const [ackFilter, setAckFilter] = useState<'UNACK' | 'ALL' | 'ACK'>('UNACK');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isBulkDialogOpen, setIsBulkDialogOpen] = useState(false);

  const { data: alerts, isLoading, refetch, isFetching } = useAlerts();
  const ackMutation = useAcknowledgeAlert();
  const bulkAckMutation = useBulkAcknowledgeAlerts();

  // Filtered alerts
  const filteredAlerts = useMemo(() => {
    if (!alerts) return [];
    const query = searchQuery.trim().toLowerCase();
    const todayStr = new Date().toISOString().split('T')[0];
    return alerts.filter((a: Alert) => {
      // The ones which are expired should not be in the alert section
      if (a.batch_status === 'EXPIRED') return false;
      if (a.expiry_date && a.expiry_date < todayStr) return false;
      if (a.message && /\b(has expired|is expired|expired on)\b/i.test(a.message)) return false;

      const matchesSeverity =
        severityFilter === 'ALL' || a.severity === severityFilter;
      const matchesAck =
        ackFilter === 'ALL' ||
        (ackFilter === 'UNACK' && !a.is_acknowledged) ||
        (ackFilter === 'ACK' && a.is_acknowledged);
      const matchesQuery =
        !query ||
        (a.product_name && a.product_name.toLowerCase().includes(query)) ||
        (a.batch_code && a.batch_code.toLowerCase().includes(query)) ||
        (a.message && a.message.toLowerCase().includes(query));
      return matchesSeverity && matchesAck && matchesQuery;
    });
  }, [alerts, severityFilter, ackFilter, searchQuery]);

  const unacknowledgedIds = useMemo(() => {
    if (!alerts) return [];
    const todayStr = new Date().toISOString().split('T')[0];
    return alerts
      .filter((a: Alert) => {
        if (a.is_acknowledged) return false;
        if (a.batch_status === 'EXPIRED') return false;
        if (a.expiry_date && a.expiry_date < todayStr) return false;
        if (a.message && /\b(has expired|is expired|expired on)\b/i.test(a.message)) return false;
        return true;
      })
      .map((a: Alert) => a.id);
  }, [alerts]);

  const handleSingleAcknowledge = (id: number) => {
    ackMutation.mutate(id, {
      onSuccess: () => onTriggerToast('Alert acknowledged by staff'),
    });
  };

  const handleBulkAcknowledge = () => {
    if (unacknowledgedIds.length === 0) return;
    bulkAckMutation.mutate(unacknowledgedIds, {
      onSuccess: () => {
        setIsBulkDialogOpen(false);
        onTriggerToast(`Acknowledged ${unacknowledgedIds.length} active alerts`);
      },
    });
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <PageHeader
        title="Stock &amp; Spoilage Alerts"
        description="Review critical shelf-life horizons (<7 days to expiry), stock threshold violations, and automated inventory triage alerts."
        action={
          <div className="flex items-center gap-2.5">
            <Button
              variant="outline"
              size="sm"
              disabled={isFetching}
              onClick={() => {
                refetch();
                onTriggerToast('Checking shelf horizons & refreshing alerts...');
              }}
              className="gap-1.5"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </Button>
            <Button
              variant="primary"
              size="sm"
              disabled={unacknowledgedIds.length === 0 || bulkAckMutation.isPending}
              onClick={() => setIsBulkDialogOpen(true)}
              className="gap-1.5"
            >
              <CheckCheck className="w-4 h-4" />
              <span>Acknowledge All ({unacknowledgedIds.length})</span>
            </Button>
          </div>
        }
      />

      {/* Filter and Search Bar */}
      <div className="flex flex-col gap-3 border-b border-[var(--border)] pb-3">
        {/* Quick Search */}
        <div className="relative w-full">
          <Search className="w-4 h-4 text-[var(--muted)] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by product (e.g. Curd Cup, Green Peas, Veg Puff), batch code (e.g. B261017-0028)..."
            className="w-full pl-9 pr-14 py-2 text-xs rounded-[8px] bg-[var(--surface)] border border-[var(--border)] text-[var(--text)] placeholder-[var(--muted)] focus:outline-none focus:border-[var(--primary)] transition-all shadow-xs"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[11px] text-[var(--muted)] hover:text-[var(--text)] font-medium px-1.5 py-0.5 rounded bg-[var(--surface-2)] border border-[var(--border)]"
            >
              Clear
            </button>
          )}
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          {/* Severity Filter */}
          <div className="flex items-center gap-1.5 flex-wrap text-xs">
            <span className="text-[var(--muted)] text-[11px] font-medium mr-1 flex items-center gap-1">
              <Filter className="w-3.5 h-3.5" />
              Severity:
            </span>
            {[
              { id: 'ALL', label: 'All Severities' },
              { id: 'CRITICAL', label: 'Critical' },
              { id: 'WARNING', label: 'Warning' },
              { id: 'INFO', label: 'Info' },
            ].map((sev) => (
              <button
                key={sev.id}
                type="button"
                onClick={() => setSeverityFilter(sev.id)}
                className={`px-3 py-1.5 rounded-[6px] text-xs font-semibold border transition-all ${
                  severityFilter === sev.id
                    ? 'bg-[var(--primary)] text-white border-[var(--primary)] shadow-xs'
                    : 'bg-[var(--surface)] text-[var(--muted)] border-[var(--border)] hover:text-[var(--text)]'
                }`}
              >
                {sev.label}
              </button>
            ))}
          </div>

          {/* Status Filter */}
          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-[var(--muted)] text-[11px] font-medium mr-1">Status:</span>
            {[
              { id: 'UNACK', label: 'Active Unresolved' },
              { id: 'ACK', label: 'Acknowledged' },
              { id: 'ALL', label: 'All' },
            ].map((st) => (
              <button
                key={st.id}
                type="button"
                onClick={() => setAckFilter(st.id as 'UNACK' | 'ACK' | 'ALL')}
                className={`px-2.5 py-1 rounded-[6px] text-[11px] font-semibold border transition-all ${
                  ackFilter === st.id
                    ? 'bg-[var(--surface-2)] text-[var(--text)] border-[var(--primary)]'
                    : 'bg-[var(--surface)] text-[var(--muted)] border-[var(--border)] hover:text-[var(--text)]'
                }`}
              >
                {st.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Alerts Grid / Card List */}
      {isLoading ? (
        <div className="space-y-3 py-4">
          <div className="h-20 rounded-[10px] bg-[var(--surface)] border border-[var(--border)] animate-pulse" />
          <div className="h-20 rounded-[10px] bg-[var(--surface)] border border-[var(--border)] animate-pulse" />
          <div className="h-20 rounded-[10px] bg-[var(--surface)] border border-[var(--border)] animate-pulse" />
        </div>
      ) : filteredAlerts.length === 0 ? (
        <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-[var(--surface-2)] text-[var(--color-success)] flex items-center justify-center mx-auto border border-[var(--border)]">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-[var(--text)]">No Alerts Found</h3>
          <p className="text-xs text-[var(--muted)] max-w-sm mx-auto">
            All inventory horizons match your current filter parameters with no unacknowledged threshold warnings.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredAlerts.map((a: Alert) => (
            <div
              key={a.id}
              className={`p-4 sm:p-5 rounded-[12px] border bg-[var(--surface)] flex flex-col sm:flex-row sm:items-center justify-between gap-4 transition-all ${
                !a.is_acknowledged
                  ? 'border-[var(--border)] shadow-xs hover:border-[var(--primary)]/50'
                  : 'border-[var(--border)]/60 opacity-70 bg-[var(--surface)]/50'
              }`}
            >
              <div className="flex items-start gap-3.5 min-w-0">
                <div
                  className={`w-9 h-9 rounded-[8px] flex items-center justify-center shrink-0 ${
                    a.severity === 'CRITICAL'
                      ? 'bg-[var(--color-danger-subtle)] text-[var(--color-danger)]'
                      : a.severity === 'WARNING'
                      ? 'bg-[var(--color-warning-subtle)] text-[var(--color-warning)]'
                      : 'bg-[var(--color-info-subtle)] text-[var(--color-info)]'
                  }`}
                >
                  {a.severity === 'CRITICAL' ? (
                    <ShieldAlert className="w-5 h-5" />
                  ) : a.severity === 'WARNING' ? (
                    <AlertTriangle className="w-5 h-5" />
                  ) : (
                    <Info className="w-5 h-5" />
                  )}
                </div>

                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <StatusBadge
                      status={a.severity}
                      variant={
                        a.severity === 'CRITICAL'
                          ? 'danger'
                          : a.severity === 'WARNING'
                          ? 'warning'
                          : 'info'
                      }
                    >
                      {a.severity}
                    </StatusBadge>
                    <span className="font-semibold text-xs text-[var(--text)] truncate">
                      {a.product_name || (a.batch ? `Batch #${a.batch}` : 'Inventory Alert')}
                    </span>
                    {a.batch_code && (
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[var(--surface-2)] text-[var(--muted)] border border-[var(--border)]">
                        {a.batch_code}
                      </span>
                    )}
                    <span className="text-[11px] text-[var(--muted)] flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      <span>{new Date(a.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </span>
                  </div>
                  <p className="text-xs text-[var(--text)] leading-relaxed">{a.message}</p>
                </div>
              </div>

              {/* Action */}
              <div className="flex items-center gap-2.5 sm:self-center shrink-0 pl-12 sm:pl-0">
                {a.is_acknowledged ? (
                  <span className="text-[11px] text-[var(--color-success)] font-semibold flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Acknowledged</span>
                  </span>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={ackMutation.isPending}
                    onClick={() => handleSingleAcknowledge(a.id)}
                    className="text-xs h-8 px-3"
                  >
                    Acknowledge
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Bulk Acknowledge Confirmation Dialog */}
      <ConfirmDialog
        isOpen={isBulkDialogOpen}
        title="Acknowledge All Critical Alerts"
        description={`Are you sure you want to mark all ${unacknowledgedIds.length} active inventory alerts as acknowledged? This documents that operating staff has reviewed the expiring stock batches.`}
        confirmLabel="Acknowledge All"
        variant="warning"
        onConfirm={handleBulkAcknowledge}
        onCancel={() => setIsBulkDialogOpen(false)}
      />
    </div>
  );
};

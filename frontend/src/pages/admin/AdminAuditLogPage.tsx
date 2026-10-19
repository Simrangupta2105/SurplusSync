import React, { useState } from 'react';
import {
  FileText,
  Search,
  Filter,
  Shield,
  Eye,

  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Ban,
  XCircle,
} from 'lucide-react';
import { PageHeader } from '../../components/ui/PageHeader';
import { Button } from '../../components/ui/Button';
import { Skeleton } from '../../components/ui/Skeleton';
import { EmptyState } from '../../components/ui/EmptyState';
import { useAdminAuditLogs } from '../../hooks/useData';
import type { AdminAuditLog } from '../../types';

export const AdminAuditLogPage: React.FC = () => {
  const [search, setSearch] = useState('');
  const [actionFilter, setActionFilter] = useState('ALL');
  const [selectedLog, setSelectedLog] = useState<AdminAuditLog | null>(null);

  const { data: logsResponse, isLoading } = useAdminAuditLogs({
    action: actionFilter === 'ALL' ? undefined : actionFilter,
    search: search.trim() || undefined,
  });

  const logs = logsResponse?.results || [];

  const getActionBadge = (action: string) => {
    switch (action) {
      case 'VERIFY_NGO':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-500">
            <CheckCircle2 className="w-3 h-3" /> VERIFY NGO
          </span>
        );
      case 'REJECT_NGO':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-neutral-500/10 text-neutral-400">
            <XCircle className="w-3 h-3" /> REJECT NGO
          </span>
        );
      case 'SUSPEND_ORG':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-500/10 text-red-500">
            <Ban className="w-3 h-3" /> SUSPEND ORG
          </span>
        );
      case 'REINSTATE_ORG':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-500">
            <RotateCcw className="w-3 h-3" /> REINSTATE ORG
          </span>
        );
      case 'HIDE_RATING':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-500">
            <AlertTriangle className="w-3 h-3" /> HIDE RATING
          </span>
        );
      case 'UNHIDE_RATING':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-500">
            <CheckCircle2 className="w-3 h-3" /> UNHIDE RATING
          </span>
        );
      case 'UPDATE_ISSUE':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400">
            <FileText className="w-3 h-3" /> UPDATE ISSUE
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-[var(--surface-2)] text-[var(--muted)]">
            {action}
          </span>
        );
    }
  };

  const getLogSummary = (details?: Record<string, unknown>) => {
    if (!details) return '—';
    if (typeof details.reason === 'string') return details.reason;
    if (typeof details.note === 'string') return details.note;
    if (typeof details.admin_notes === 'string') return details.admin_notes;
    return JSON.stringify(details);
  };


  return (
    <div className="space-y-6 pb-8 animate-in fade-in duration-150">
      <PageHeader
        title="Administrative Audit Log"
        subtitle="Immutable security trail of all administrative state modifications and moderation events"
      />

      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-[var(--surface)] p-3 rounded-[12px] border border-[var(--border)]">
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
          <input
            type="text"
            placeholder="Search audit trail..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full text-xs pl-9 pr-3 py-1.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Filter className="w-4 h-4 text-[var(--muted)] shrink-0 hidden sm:block" />
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="text-xs px-2.5 py-1.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)] w-full sm:w-auto"
          >
            <option value="ALL">All Actions</option>
            <option value="VERIFY_NGO">Verify NGO</option>
            <option value="REJECT_NGO">Reject NGO</option>
            <option value="SUSPEND_ORG">Suspend Org</option>
            <option value="REINSTATE_ORG">Reinstate Org</option>
            <option value="HIDE_RATING">Hide Rating</option>
            <option value="UNHIDE_RATING">Unhide Rating</option>
            <option value="UPDATE_ISSUE">Update Issue</option>
          </select>
        </div>
      </div>

      {/* Table & Cards */}
      {isLoading ? (
        <div className="space-y-3">
          <Skeleton variant="card" className="h-16" />
          <Skeleton variant="card" className="h-16" />
          <Skeleton variant="card" className="h-16" />
        </div>
      ) : logs.length === 0 ? (
        <div className="bg-[var(--surface)] rounded-[12px] border border-[var(--border)] p-12">
          <EmptyState
            icon={Shield}
            title="No audit entries found"
            description="No administrative logs match your current query."
          />
        </div>
      ) : (
        <>
          {/* Desktop Table View */}
          <div className="hidden md:block rounded-[12px] border border-[var(--border)] bg-[var(--surface)] overflow-hidden shadow-xs">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[var(--border)] bg-[var(--surface-2)] text-[11px] font-bold uppercase tracking-wider text-[var(--muted)]">
                  <th className="px-5 py-3.5">Timestamp</th>
                  <th className="px-5 py-3.5">Admin User</th>
                  <th className="px-5 py-3.5">Action</th>
                  <th className="px-5 py-3.5">Target</th>
                  <th className="px-5 py-3.5">Summary</th>
                  <th className="px-5 py-3.5 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)] text-xs">
                {logs.map((log) => (
                  <tr
                    key={log.id}
                    onClick={() => setSelectedLog(log)}
                    className="hover:bg-[var(--surface-2)]/60 transition-colors cursor-pointer"
                  >
                    <td className="px-5 py-4 text-[var(--muted)] whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="px-5 py-4">
                      <p className="font-bold text-[var(--text)]">{log.admin_username}</p>
                      <p className="text-[11px] text-[var(--muted)]">{log.admin_email}</p>
                    </td>
                    <td className="px-5 py-4">{getActionBadge(log.action)}</td>
                    <td className="px-5 py-4 font-mono text-[11px] text-[var(--text)]">
                      {log.target_type} #{log.target_id}
                    </td>
                    <td className="px-5 py-4 text-[var(--muted)] max-w-xs truncate">
                      {getLogSummary(log.details)}
                    </td>

                    <td className="px-5 py-4 text-right" onClick={(e) => e.stopPropagation()}>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setSelectedLog(log)}
                        className="text-xs h-7 px-2"
                      >
                        <Eye className="w-3.5 h-3.5 mr-1" /> Inspect
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile Card View */}
          <div className="grid grid-cols-1 gap-3 md:hidden">
            {logs.map((log) => (
              <div
                key={log.id}
                onClick={() => setSelectedLog(log)}
                className="bg-[var(--surface)] p-4 rounded-[12px] border border-[var(--border)] shadow-xs space-y-2 cursor-pointer"
              >
                <div className="flex items-center justify-between">
                  {getActionBadge(log.action)}
                  <span className="text-[10px] text-[var(--muted)]">
                    {new Date(log.created_at).toLocaleDateString()}
                  </span>
                </div>

                <div className="text-xs">
                  <span className="font-semibold text-[var(--text)]">
                    {log.admin_username}
                  </span>{' '}
                  <span className="text-[var(--muted)]">modified</span>{' '}
                  <span className="font-mono text-[var(--text)]">
                    {log.target_type} #{log.target_id}
                  </span>
                </div>

                <p className="text-xs text-[var(--muted)] truncate">
                  {getLogSummary(log.details)}
                </p>

              </div>
            ))}
          </div>
        </>
      )}

      {/* Audit Log JSON Inspector Modal */}
      {selectedLog && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150"
        >
          <div className="w-full max-w-lg rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Shield className="w-5 h-5 text-[var(--primary)]" />
                <h3 className="text-sm font-bold text-[var(--text)]">Audit Record #{selectedLog.id}</h3>
              </div>
              {getActionBadge(selectedLog.action)}
            </div>

            <div className="space-y-2 text-xs">
              <div className="grid grid-cols-2 gap-2 p-3 rounded-[8px] bg-[var(--surface-2)]">
                <div>
                  <span className="text-[11px] font-semibold text-[var(--muted)] block">Admin:</span>
                  <span className="font-medium text-[var(--text)]">{selectedLog.admin_username} ({selectedLog.admin_email})</span>
                </div>
                <div>
                  <span className="text-[11px] font-semibold text-[var(--muted)] block">Timestamp:</span>
                  <span className="font-medium text-[var(--text)]">{new Date(selectedLog.created_at).toLocaleString()}</span>
                </div>
                <div className="col-span-2 pt-1 border-t border-[var(--border)]">
                  <span className="text-[11px] font-semibold text-[var(--muted)] block">Target Entity:</span>
                  <span className="font-mono font-medium text-[var(--text)]">{selectedLog.target_type} ID #{selectedLog.target_id}</span>
                </div>
              </div>

              <div>
                <label className="text-[11px] font-bold uppercase text-[var(--muted)] block mb-1">
                  Metadata & Event Payload (JSON)
                </label>
                <pre className="p-3 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] font-mono text-[11px] text-[var(--text)] overflow-x-auto max-h-48">
                  {JSON.stringify(selectedLog.details, null, 2)}
                </pre>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <Button variant="outline" size="sm" onClick={() => setSelectedLog(null)}>
                Dismiss
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

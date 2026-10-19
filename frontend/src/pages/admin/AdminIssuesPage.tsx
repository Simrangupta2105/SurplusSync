import React, { useState } from 'react';
import {
  AlertTriangle,
  Search,
  CheckCircle2,
  Clock,
  Eye,
  MessageSquare,
  ArrowRight,
  Send,
  XCircle,
} from 'lucide-react';
import { PageHeader } from '../../components/ui/PageHeader';
import { Button } from '../../components/ui/Button';
import { Sheet } from '../../components/ui/Sheet';
import { Skeleton } from '../../components/ui/Skeleton';
import { EmptyState } from '../../components/ui/EmptyState';
import { useAdminIssues, useUpdateAdminIssue } from '../../hooks/useData';
import type { AdminIssue, IssueStatus, IssuePriority } from '../../types';


interface AdminIssuesPageProps {
  onTriggerToast?: (message: string) => void;
}

export const AdminIssuesPage: React.FC<AdminIssuesPageProps> = ({ onTriggerToast }) => {
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [priorityFilter, setPriorityFilter] = useState<string>('ALL');
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');
  const [search, setSearch] = useState('');

  // Selected issue for detail drawer
  const [selectedIssue, setSelectedIssue] = useState<AdminIssue | null>(null);
  const [editStatus, setEditStatus] = useState<IssueStatus>('OPEN');
  const [editPriority, setEditPriority] = useState<IssuePriority>('MEDIUM');
  const [editNotes, setEditNotes] = useState<string>('');

  const { data: issuesResponse, isLoading } = useAdminIssues({
    status: statusFilter === 'ALL' ? undefined : statusFilter,
    priority: priorityFilter === 'ALL' ? undefined : priorityFilter,
    category: categoryFilter === 'ALL' ? undefined : categoryFilter,
    search: search.trim() || undefined,
  });

  const updateIssueMutation = useUpdateAdminIssue();

  const issues = issuesResponse?.results || [];

  const handleOpenDrawer = (issue: AdminIssue) => {
    setSelectedIssue(issue);
    setEditStatus(issue.status);
    setEditPriority(issue.priority);
    setEditNotes(issue.admin_notes || '');
  };

  const handleSaveChanges = async (overrideStatus?: IssueStatus) => {
    if (!selectedIssue) return;
    const finalStatus = overrideStatus || editStatus;
    try {
      const updated = await updateIssueMutation.mutateAsync({
        id: selectedIssue.id,
        patch: {
          status: finalStatus,
          priority: editPriority,
          admin_notes: editNotes,
        },
      });
      setSelectedIssue(updated);
      setEditStatus(updated.status);
      onTriggerToast?.(`Issue #${selectedIssue.id} updated successfully.`);
    } catch {
      onTriggerToast?.('Failed to update issue.');
    }
  };

  const getPriorityBadge = (priority: IssuePriority) => {
    switch (priority) {
      case 'CRITICAL':
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-500/10 text-red-500">
            CRITICAL
          </span>
        );
      case 'HIGH':
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-500">
            HIGH
          </span>
        );
      case 'MEDIUM':
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-500/10 text-blue-500">
            MEDIUM
          </span>
        );
      case 'LOW':
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-neutral-500/10 text-neutral-400">
            LOW
          </span>
        );
    }
  };

  const getStatusBadge = (status: IssueStatus) => {
    switch (status) {
      case 'OPEN':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-red-500/10 text-red-500">
            <AlertTriangle className="w-3 h-3" /> Open
          </span>
        );
      case 'IN_REVIEW':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-500">
            <Clock className="w-3 h-3" /> In Review
          </span>
        );
      case 'RESOLVED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-500">
            <CheckCircle2 className="w-3 h-3" /> Resolved
          </span>
        );
      case 'DISMISSED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-neutral-500/10 text-neutral-400">
            <XCircle className="w-3 h-3" /> Dismissed
          </span>
        );
    }
  };

  return (
    <div className="space-y-6 pb-8 animate-in fade-in duration-150">
      <PageHeader
        title="Incident & Dispute Management"
        subtitle="Investigate food quality concerns, delivery disputes, and platform violations"
      />

      {/* Filter Toolbar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 bg-[var(--surface)] p-3 rounded-[12px] border border-[var(--border)]">
        {/* Search */}
        <div className="relative w-full lg:w-72">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
          <input
            type="text"
            placeholder="Search tickets, reporters, orgs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full text-xs pl-9 pr-3 py-1.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
          />
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs px-2.5 py-1.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
          >
            <option value="ALL">All Statuses</option>
            <option value="OPEN">Open</option>
            <option value="IN_REVIEW">In Review</option>
            <option value="RESOLVED">Resolved</option>
            <option value="DISMISSED">Dismissed</option>
          </select>

          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="text-xs px-2.5 py-1.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
          >
            <option value="ALL">All Priorities</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>

          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="text-xs px-2.5 py-1.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
          >
            <option value="ALL">All Categories</option>
            <option value="FOOD_QUALITY">Food Quality</option>
            <option value="NO_SHOW">No Show</option>
            <option value="WRONG_QUANTITY">Wrong Quantity</option>
            <option value="ABUSE">Abuse</option>
            <option value="TECHNICAL">Technical</option>
            <option value="OTHER">Other</option>
          </select>
        </div>
      </div>

      {/* Issues Content */}
      {isLoading ? (
        <div className="space-y-3">
          <Skeleton variant="card" className="h-16" />
          <Skeleton variant="card" className="h-16" />
          <Skeleton variant="card" className="h-16" />
        </div>
      ) : issues.length === 0 ? (
        <div className="bg-[var(--surface)] rounded-[12px] border border-[var(--border)] p-12">
          <EmptyState
            icon={CheckCircle2}
            title="No issues found"
            description="No incident reports match your current filters. The network is running smoothly."
          />
        </div>
      ) : (
        <>
          {/* Desktop Table View */}
          <div className="hidden md:block rounded-[12px] border border-[var(--border)] bg-[var(--surface)] overflow-hidden shadow-xs">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[var(--border)] bg-[var(--surface-2)] text-[11px] font-bold uppercase tracking-wider text-[var(--muted)]">
                  <th className="px-5 py-3.5">Ticket</th>
                  <th className="px-5 py-3.5">Category</th>
                  <th className="px-5 py-3.5">Priority</th>
                  <th className="px-5 py-3.5">Reporter Org</th>
                  <th className="px-5 py-3.5">Target Org</th>
                  <th className="px-5 py-3.5">Status</th>
                  <th className="px-5 py-3.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)] text-xs">
                {issues.map((issue) => (
                  <tr
                    key={issue.id}
                    onClick={() => handleOpenDrawer(issue)}
                    className="hover:bg-[var(--surface-2)]/60 transition-colors cursor-pointer group"
                  >
                    <td className="px-5 py-4">
                      <div>
                        <p className="font-bold text-[var(--text)] group-hover:text-[var(--primary)] transition-colors">
                          #{issue.id}
                        </p>
                        <p className="text-[11px] text-[var(--muted)] truncate max-w-[200px]">
                          {issue.description}
                        </p>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <span className="font-mono text-[11px] text-[var(--text)]">
                        {issue.category.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-5 py-4">{getPriorityBadge(issue.priority)}</td>
                    <td className="px-5 py-4">
                      <p className="font-semibold text-[var(--text)]">
                        {issue.reporter_org_name}
                      </p>
                      <p className="text-[10px] text-[var(--muted)]">{issue.reporter_org_type}</p>
                    </td>
                    <td className="px-5 py-4 text-[var(--muted)]">
                      {issue.target_org_name ? (
                        <div>
                          <p className="font-medium text-[var(--text)]">
                            {issue.target_org_name}
                          </p>
                          <p className="text-[10px] text-[var(--muted)]">{issue.target_org_type}</p>
                        </div>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="px-5 py-4">{getStatusBadge(issue.status)}</td>
                    <td className="px-5 py-4 text-right" onClick={(e) => e.stopPropagation()}>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleOpenDrawer(issue)}
                        className="text-xs h-7 px-2"
                      >
                        <Eye className="w-3.5 h-3.5 mr-1" /> Review
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile Card View */}
          <div className="grid grid-cols-1 gap-3 md:hidden">
            {issues.map((issue) => (
              <div
                key={issue.id}
                onClick={() => handleOpenDrawer(issue)}
                className="bg-[var(--surface)] p-4 rounded-[12px] border border-[var(--border)] shadow-xs space-y-3 cursor-pointer"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-xs text-[var(--text)]">#{issue.id}</span>
                    {getPriorityBadge(issue.priority)}
                  </div>
                  {getStatusBadge(issue.status)}
                </div>

                <p className="text-xs text-[var(--text)] font-medium line-clamp-2">
                  {issue.description}
                </p>

                <div className="flex items-center justify-between text-[11px] text-[var(--muted)] pt-2 border-t border-[var(--border)]">
                  <span>From: {issue.reporter_org_name}</span>
                  <span className="text-[var(--primary)] font-semibold inline-flex items-center">
                    Review <ArrowRight className="w-3 h-3 ml-1" />
                  </span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Issue Detail Drawer Sheet */}
      <Sheet
        isOpen={!!selectedIssue}
        onClose={() => setSelectedIssue(null)}
        title={`Incident Ticket #${selectedIssue?.id}`}
        description={`Category: ${selectedIssue?.category.replace('_', ' ') || 'General'}`}
        width="lg"
        footer={
          selectedIssue && (
            <div className="flex items-center justify-between w-full">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedIssue(null)}
                className="text-xs"
              >
                Close
              </Button>
              <div className="flex items-center gap-2">
                {selectedIssue.status !== 'RESOLVED' && (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => handleSaveChanges('RESOLVED')}
                    disabled={updateIssueMutation.isPending}
                    className="text-xs bg-emerald-600 hover:bg-emerald-700"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                    Mark Resolved
                  </Button>
                )}
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => handleSaveChanges()}
                  disabled={updateIssueMutation.isPending}
                  className="text-xs"
                >
                  <Send className="w-3.5 h-3.5 mr-1" />
                  Save Changes
                </Button>
              </div>
            </div>
          )
        }
      >
        {selectedIssue && (
          <div className="space-y-6 py-2 text-xs">
            {/* Status & Priority Selectors */}
            <div className="grid grid-cols-2 gap-3 p-4 rounded-[10px] bg-[var(--surface-2)] border border-[var(--border)]">
              <div>
                <label className="text-[11px] font-bold uppercase text-[var(--muted)] block mb-1">
                  Status
                </label>
                <select
                  value={editStatus}
                  onChange={(e) => setEditStatus(e.target.value as IssueStatus)}
                  className="w-full text-xs p-2 rounded-[6px] bg-[var(--surface)] border border-[var(--border)] text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
                >
                  <option value="OPEN">OPEN</option>
                  <option value="IN_REVIEW">IN REVIEW</option>
                  <option value="RESOLVED">RESOLVED</option>
                  <option value="DISMISSED">DISMISSED</option>
                </select>
              </div>

              <div>
                <label className="text-[11px] font-bold uppercase text-[var(--muted)] block mb-1">
                  Priority
                </label>
                <select
                  value={editPriority}
                  onChange={(e) => setEditPriority(e.target.value as IssuePriority)}
                  className="w-full text-xs p-2 rounded-[6px] bg-[var(--surface)] border border-[var(--border)] text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
                >
                  <option value="LOW">LOW</option>
                  <option value="MEDIUM">MEDIUM</option>
                  <option value="HIGH">HIGH</option>
                  <option value="CRITICAL">CRITICAL</option>
                </select>
              </div>
            </div>

            {/* Reporter & Target Orgs Card */}
            <div className="p-4 rounded-[10px] bg-[var(--surface-2)] border border-[var(--border)] space-y-3">
              <h4 className="font-bold text-sm text-[var(--text)]">Incident Parties</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <span className="text-[11px] font-semibold text-[var(--muted)] block">
                    Reported By:
                  </span>
                  <p className="font-bold text-[var(--text)]">{selectedIssue.reporter_org_name}</p>
                  <p className="text-[11px] text-[var(--muted)]">
                    {selectedIssue.reporter_name} ({selectedIssue.reporter_org_type})
                  </p>
                </div>

                <div>
                  <span className="text-[11px] font-semibold text-[var(--muted)] block">
                    Against / Target:
                  </span>
                  <p className="font-bold text-[var(--text)]">
                    {selectedIssue.target_org_name || 'Network General'}
                  </p>
                  <p className="text-[11px] text-[var(--muted)]">
                    {selectedIssue.target_org_type || '—'}
                  </p>
                </div>
              </div>

              {selectedIssue.claim_title && (
                <div className="pt-2 border-t border-[var(--border)]">
                  <span className="text-[11px] font-semibold text-[var(--muted)] block">
                    Related Claim:
                  </span>
                  <p className="text-[var(--text)] font-mono">{selectedIssue.claim_title}</p>
                </div>
              )}
            </div>

            {/* Incident Description */}
            <div className="space-y-1.5">
              <h4 className="font-bold text-sm text-[var(--text)]">Incident Description</h4>
              <div className="p-3.5 rounded-[8px] bg-[var(--surface)] border border-[var(--border)] text-[var(--text)] leading-relaxed">
                {selectedIssue.description}
              </div>
            </div>

            {/* Admin Notes */}
            <div className="space-y-1.5">
              <h4 className="font-bold text-sm text-[var(--text)] flex items-center gap-1.5">
                <MessageSquare className="w-4 h-4 text-[var(--primary)]" />
                Administrative Resolution Notes
              </h4>
              <p className="text-[11px] text-[var(--muted)]">
                Internal notes, escalation rationale, and correspondence with organizations.
              </p>
              <textarea
                value={editNotes}
                onChange={(e) => setEditNotes(e.target.value)}
                placeholder="Log your investigation findings, contact logs, or resolution actions..."
                rows={4}
                className="w-full text-xs rounded-[8px] border border-[var(--border)] bg-[var(--surface)] p-3 text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
              />
            </div>
          </div>
        )}
      </Sheet>
    </div>
  );
};

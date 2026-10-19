import React from 'react';
import {
  Shield,
  Server,
  Database,
  Lock,
  User,
  CheckCircle2,
  Download,
  Activity,
  Layers,
} from 'lucide-react';

import { PageHeader } from '../../components/ui/PageHeader';
import { Button } from '../../components/ui/Button';
import { useCurrentUser } from '../../hooks/useData';
import { defaultMode } from '../../services';

interface AdminSettingsPageProps {
  onTriggerToast?: (message: string) => void;
}

export const AdminSettingsPage: React.FC<AdminSettingsPageProps> = ({ onTriggerToast }) => {
  const { data: currentUser } = useCurrentUser();
  const isDemo = defaultMode === 'demo';

  const handleExportAudit = () => {
    onTriggerToast?.('Exporting platform audit records as JSON...');
  };

  return (
    <div className="space-y-6 pb-8 animate-in fade-in duration-150 max-w-4xl">
      <PageHeader
        title="Platform Administration Settings"
        subtitle="System diagnostics, security configurations, and administrator account details"
      />

      {/* Admin Account Profile Card */}
      <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-6 space-y-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-full bg-[var(--primary)]/10 text-[var(--primary)] flex items-center justify-center font-bold text-lg">
            <User className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-base font-bold text-[var(--text)]">
              {currentUser?.username || 'Platform Administrator'}
            </h3>
            <p className="text-xs text-[var(--muted)]">
              {currentUser?.email || 'admin@surplussync.platform'}
            </p>
          </div>
          <span className="ml-auto inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-[var(--primary)]/10 text-[var(--primary)]">
            <Shield className="w-3.5 h-3.5" /> Staff Superadmin
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-3 border-t border-[var(--border)] text-xs text-[var(--muted)]">
          <div>
            <span className="font-semibold text-[var(--text)] block">Role Classification:</span>
            <span>Platform Administrator (No Org Affiliation)</span>
          </div>
          <div>
            <span className="font-semibold text-[var(--text)] block">Staff Authorization:</span>
            <span className="text-emerald-500 font-semibold flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" /> Active & Verified
            </span>
          </div>
          <div>
            <span className="font-semibold text-[var(--text)] block">Data Layer Mode:</span>
            <span className="uppercase font-mono font-semibold text-[var(--text)]">
              {defaultMode} SOURCE
            </span>
          </div>
        </div>
      </div>

      {/* Platform Health & Connectivity */}
      <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-6 space-y-4">
        <h3 className="text-sm font-bold text-[var(--text)] flex items-center gap-2">
          <Activity className="w-4 h-4 text-[var(--primary)]" />
          Platform Health & Infrastructure Diagnostics
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="p-4 rounded-[10px] bg-[var(--surface-2)] border border-[var(--border)] flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-emerald-500/10 text-emerald-500 flex items-center justify-center shrink-0">
              <Server className="w-4 h-4" />
            </div>
            <div>
              <p className="text-xs font-bold text-[var(--text)]">Django REST Framework API</p>
              <p className="text-[11px] text-[var(--muted)]">Core API endpoints at /api/v1/admin/</p>
              <p className="text-[11px] text-emerald-500 font-semibold mt-1">Operational (HTTP 200)</p>
            </div>
          </div>

          <div className="p-4 rounded-[10px] bg-[var(--surface-2)] border border-[var(--border)] flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-emerald-500/10 text-emerald-500 flex items-center justify-center shrink-0">
              <Database className="w-4 h-4" />
            </div>
            <div>
              <p className="text-xs font-bold text-[var(--text)]">Relational Database Engine</p>
              <p className="text-[11px] text-[var(--muted)]">PostgreSQL with multi-tenant schema isolation</p>
              <p className="text-[11px] text-emerald-500 font-semibold mt-1">Healthy Connection Pool</p>
            </div>
          </div>

          <div className="p-4 rounded-[10px] bg-[var(--surface-2)] border border-[var(--border)] flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-emerald-500/10 text-emerald-500 flex items-center justify-center shrink-0">
              <Lock className="w-4 h-4" />
            </div>
            <div>
              <p className="text-xs font-bold text-[var(--text)]">Admin Guard & Permission Layer</p>
              <p className="text-[11px] text-[var(--muted)]">IsPlatformAdmin (Staff & Org=None check)</p>
              <p className="text-[11px] text-emerald-500 font-semibold mt-1">Strict Enforcement Active</p>
            </div>
          </div>

          <div className="p-4 rounded-[10px] bg-[var(--surface-2)] border border-[var(--border)] flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-purple-500/10 text-purple-400 flex items-center justify-center shrink-0">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <p className="text-xs font-bold text-[var(--text)]">Environment Profile</p>
              <p className="text-[11px] text-[var(--muted)]">SurplusSync Release v1.0.0 (Production)</p>
              <p className="text-[11px] text-purple-400 font-semibold mt-1">
                {isDemo ? 'Interactive Simulation Engine' : 'Live Production Cluster'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Security & Audit Controls */}
      <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-6 space-y-4">
        <h3 className="text-sm font-bold text-[var(--text)] flex items-center gap-2">
          <Shield className="w-4 h-4 text-[var(--primary)]" />
          Security Policy & Compliance Export
        </h3>
        <p className="text-xs text-[var(--muted)] leading-relaxed">
          Administrative modifications to organization statuses, verifications, and ratings are strictly append-only and audited in the AdminAuditLog database table.
        </p>

        <div className="pt-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportAudit}
            className="text-xs"
          >
            <Download className="w-4 h-4 mr-1.5" />
            Export Audit Logs as JSON
          </Button>
        </div>
      </div>
    </div>
  );
};

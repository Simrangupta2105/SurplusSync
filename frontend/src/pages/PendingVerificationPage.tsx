import React from 'react';
import { Clock, ShieldCheck, LogOut, CheckCircle2 } from 'lucide-react';
import { Button } from '../components/ui/Button';

interface PendingVerificationPageProps {
  organizationName?: string;
  onLogout: () => void;
  onSwitchToBusinessDemo?: () => void;
}

export const PendingVerificationPage: React.FC<PendingVerificationPageProps> = ({
  organizationName = 'Registered NGO Partner',
  onLogout,
  onSwitchToBusinessDemo,
}) => {
  return (
    <div className="flex flex-col items-center justify-center min-h-[75vh] px-4 py-8">
      <div className="w-full max-w-lg rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-6 sm:p-8 shadow-xl text-center space-y-6">
        {/* Verification Icon Badge */}
        <div className="mx-auto w-16 h-16 rounded-full bg-[var(--color-warning-subtle)] text-[var(--color-warning)] border border-[var(--color-warning-border)] flex items-center justify-center">
          <Clock className="w-8 h-8 animate-pulse" />
        </div>

        <div className="space-y-2">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[8px] text-xs font-semibold bg-[var(--color-warning-subtle)] text-[var(--color-warning)] border border-[var(--color-warning-border)]">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-warning)]" />
            Verification in Progress
          </div>

          <h1 className="text-xl sm:text-2xl font-bold text-[var(--text)] tracking-tight">
            Account Pending Administrator Approval
          </h1>

          <p className="text-xs text-[var(--muted)] font-medium">
            Organization: <strong className="text-[var(--text)]">{organizationName}</strong>
          </p>
        </div>

        {/* Informative compliance card */}
        <div className="rounded-[8px] bg-[var(--surface-2)] p-4 text-left border border-[var(--border)] space-y-2.5 text-xs">
          <p className="text-[var(--text)] font-semibold flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-[var(--primary)] shrink-0" />
            Food Safety & Distribution Compliance
          </p>
          <p className="text-[var(--muted)] leading-relaxed">
            To safeguard community health, all NGO partners undergo verification by SurplusSync operations before being authorized to claim and collect perishable food donations.
          </p>
          <div className="pt-2 border-t border-[var(--border)] space-y-1.5 text-[11px] text-[var(--muted)]">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-3.5 h-3.5 text-[var(--color-success)] shrink-0" />
              <span>Identity & NGO Registration documentation review</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-3.5 h-3.5 text-[var(--color-success)] shrink-0" />
              <span>Cold-chain transportation readiness check</span>
            </div>
            <div className="flex items-center gap-2">
              <Clock className="w-3.5 h-3.5 text-[var(--color-warning)] shrink-0" />
              <span>Standard review turnaround: 24–48 business hours</span>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onLogout}
            className="w-full sm:w-auto gap-2"
          >
            <LogOut className="w-4 h-4" />
            <span>Sign Out</span>
          </Button>

          {onSwitchToBusinessDemo && (
            <Button
              variant="primary"
              size="sm"
              onClick={onSwitchToBusinessDemo}
              className="w-full sm:w-auto"
            >
              <span>Switch to Verified Persona (Demo)</span>
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

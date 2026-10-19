import React from 'react';
import { Clock, AlertTriangle } from 'lucide-react';
import { cn } from '../../lib/utils';

interface ExpiryPillProps {
  expiryDate: string | Date;
  className?: string;
  showIcon?: boolean;
}

function getExpiryDetails(expiryDate: string | Date): {
  hoursLeft: number;
  label: string;
  severity: 'critical' | 'urgent' | 'warning' | 'safe' | 'expired';
} {
  const target = new Date(expiryDate).getTime();
  const now = Date.now();
  const diffMs = target - now;
  const hoursLeft = Math.round(diffMs / (1000 * 60 * 60));

  if (diffMs <= 0) {
    return { hoursLeft: 0, label: 'Expired', severity: 'expired' };
  }

  if (hoursLeft < 24) {
    return {
      hoursLeft,
      label: `${hoursLeft}h left`,
      severity: 'critical',
    };
  }

  if (hoursLeft <= 48) {
    const days = Math.floor(hoursLeft / 24);
    const remHours = hoursLeft % 24;
    return {
      hoursLeft,
      label: remHours > 0 ? `${days}d ${remHours}h left` : `${days}d left`,
      severity: 'urgent',
    };
  }

  const daysLeft = Math.ceil(hoursLeft / 24);
  if (daysLeft <= 7) {
    return {
      hoursLeft,
      label: `${daysLeft}d left`,
      severity: 'warning',
    };
  }

  return {
    hoursLeft,
    label: `${daysLeft}d left`,
    severity: 'safe',
  };
}

export const ExpiryPill: React.FC<ExpiryPillProps> = ({
  expiryDate,
  className,
  showIcon = true,
}) => {
  const { label, severity } = getExpiryDetails(expiryDate);

  const severityStyles: Record<typeof severity, string> = {
    expired: 'bg-[var(--color-danger-subtle)] text-[var(--color-danger)] border-[var(--color-danger-border)]',
    critical: 'bg-[var(--color-danger-subtle)] text-[var(--color-danger)] border-[var(--color-danger-border)] font-semibold animate-pulse',
    urgent: 'bg-[var(--color-warning-subtle)] text-[var(--color-warning)] border-[var(--color-warning-border)] font-medium',
    warning: 'bg-[var(--color-info-subtle)] text-[var(--color-info)] border-[var(--color-info-border)]',
    safe: 'bg-[var(--surface-2)] text-[var(--muted)] border-[var(--border)]',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-[8px] text-[11px] border tabular-nums transition-colors',
        severityStyles[severity],
        className
      )}
    >
      {showIcon && (
        severity === 'critical' || severity === 'expired' ? (
          <AlertTriangle className="w-3 h-3 shrink-0" />
        ) : (
          <Clock className="w-3 h-3 shrink-0 opacity-75" />
        )
      )}
      <span>{label}</span>
    </span>
  );
};

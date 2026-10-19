import React from 'react';
import { cn } from '../../lib/utils';

export type StatusVariant = 'success' | 'warning' | 'danger' | 'info' | 'neutral';

interface StatusBadgeProps {
  variant?: StatusVariant;
  children?: React.ReactNode;
  dot?: boolean;
  className?: string;
  size?: 'sm' | 'md';
  status?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  variant = 'neutral',
  children,
  dot = false,
  className,
  size = 'md',
}) => {
  const variantStyles = {
    success: 'bg-[var(--color-success-bg)] text-[var(--color-success-text)] border-[var(--color-success-border)]',
    warning: 'bg-[var(--color-warning-bg)] text-[var(--color-warning-text)] border-[var(--color-warning-border)]',
    danger: 'bg-[var(--color-danger-bg)] text-[var(--color-danger-text)] border-[var(--color-danger-border)]',
    info: 'bg-[var(--color-info-bg)] text-[var(--color-info-text)] border-[var(--color-info-border)]',
    neutral: 'bg-[var(--surface-2)] text-[var(--muted)] border-[var(--border)]',
  };

  const dotColors = {
    success: 'bg-[var(--color-success)]',
    warning: 'bg-[var(--color-warning)]',
    danger: 'bg-[var(--color-danger)]',
    info: 'bg-[var(--color-info)]',
    neutral: 'bg-[var(--muted)]',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center font-medium rounded-full border transition-colors',
        size === 'sm' ? 'px-2 py-0.5 text-[11px] gap-1' : 'px-2.5 py-1 text-xs gap-1.5',
        variantStyles[variant],
        className
      )}
    >
      {dot && (
        <span
          className={cn(
            'rounded-full shrink-0',
            size === 'sm' ? 'w-1.5 h-1.5' : 'w-2 h-2',
            dotColors[variant]
          )}
        />
      )}
      {children}
    </span>
  );
};

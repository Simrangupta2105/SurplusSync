import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '../../lib/utils';

export interface StatCardProps {
  label?: string;
  title?: string;
  value: React.ReactNode;
  unit?: string;
  icon: LucideIcon;
  subText?: string;
  subtitle?: string;
  trend?: {
    value: string;
    isPositive?: boolean;
    isNeutral?: boolean;
  };
  variant?: 'default' | 'primary' | 'warning' | 'danger' | 'info';
  className?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  label,
  title,
  value,
  unit,
  icon: Icon,
  subText,
  subtitle,
  trend,
  variant = 'default',
  className,
}) => {
  const displayTitle = label || title || '';
  const displaySubtitle = subText || subtitle;
  const iconVariants = {
    default: 'bg-[var(--surface-2)] text-[var(--text)]',
    primary: 'bg-[var(--primary)]/10 text-[var(--primary)]',
    warning: 'bg-[var(--color-warning-bg)] text-[var(--color-warning)]',
    danger: 'bg-[var(--color-danger-bg)] text-[var(--color-danger)]',
    info: 'bg-[var(--color-info-bg)] text-[var(--color-info)]',
  };

  // Smart formatting of value and unit to prevent overflow
  let displayValue: React.ReactNode = value;
  let displayUnit: string | undefined = unit;

  if (typeof value === 'string') {
    // If string is like "4247.000 kg" or "1,840 kg" or "50 L"
    if (!unit) {
      const match = value.trim().match(/^(.*?)\s+([a-zA-Z%₹]+)$/);
      if (match && match[1] && !isNaN(Number(match[1].replace(/,/g, '')))) {
        displayValue = match[1];
        displayUnit = match[2];
      }
    }

    // Format raw decimal numbers like "4247.000" into "4,247"
    if (typeof displayValue === 'string') {
      const rawClean = displayValue.replace(/,/g, '').trim();
      const num = parseFloat(rawClean);
      if (!isNaN(num) && /^\d+(\.\d+)?$/.test(rawClean)) {
        displayValue = num.toLocaleString('en-IN', {
          maximumFractionDigits: num % 1 === 0 ? 0 : 2,
        });
      }
    }
  } else if (typeof value === 'number') {
    displayValue = value.toLocaleString('en-IN');
  }

  const isLongValue = typeof displayValue === 'string' && displayValue.length > 7;
  const isVeryLongValue = typeof displayValue === 'string' && displayValue.length > 14;

  return (
    <div
      className={cn(
        'bg-[var(--surface)] text-[var(--text)] rounded-[12px] p-4 sm:p-5 border border-[var(--border)] transition-colors duration-150 flex flex-col justify-between min-h-[136px] overflow-hidden',
        className
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="metric-label tracking-normal leading-tight line-clamp-2" title={displayTitle}>
          {displayTitle}
        </span>
        <div
          className={cn(
            'w-8 h-8 sm:w-9 sm:h-9 rounded-[8px] flex items-center justify-center shrink-0 transition-colors',
            iconVariants[variant]
          )}
        >
          <Icon className="w-4 h-4 sm:w-5 sm:h-5 stroke-[1.8]" />
        </div>
      </div>

      <div className="mt-2.5 min-w-0">
        <div className="flex items-baseline gap-1.5 flex-wrap min-w-0">
          <span
            className={cn(
              'metric-number text-[var(--text)] tracking-tight',
              isVeryLongValue
                ? '!text-sm !font-semibold !leading-snug truncate block w-full'
                : isLongValue && '!text-xl sm:!text-2xl'
            )}
            title={isVeryLongValue && typeof displayValue === 'string' ? displayValue : undefined}
          >
            {displayValue}
          </span>
          {displayUnit && (
            <span className="text-xs sm:text-sm font-semibold text-[var(--muted)] shrink-0">
              {displayUnit}
            </span>
          )}
        </div>

        {(trend || displaySubtitle) && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs font-normal text-[var(--muted)] min-w-0">
            {trend && (
              <span
                className={cn(
                  'inline-flex items-center gap-1 font-medium px-1.5 py-0.5 rounded-[4px] text-[11px] tabular-nums shrink-0',
                  trend.isNeutral
                    ? 'bg-[var(--surface-2)] text-[var(--muted)]'
                    : trend.isPositive
                    ? 'bg-[var(--color-success-bg)] text-[var(--color-success-text)]'
                    : 'bg-[var(--color-danger-bg)] text-[var(--color-danger-text)]'
                )}
              >
                {trend.value}
              </span>
            )}
            {displaySubtitle && (
              <span
                className="text-[11px] text-[var(--muted)] leading-tight break-words"
                title={displaySubtitle}
              >
                {displaySubtitle}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

import React from 'react';
import { PackageSearch, type LucideIcon } from 'lucide-react';
import { cn } from '../../lib/utils';

export interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  message?: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
  headingLevel?: 'h2' | 'h3' | 'p';
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon: Icon = PackageSearch,
  title,
  message,
  description,
  action,
  className,
  headingLevel = 'h2',
}) => {
  const displayMessage = description || message;
  const HeadingTag = headingLevel;

  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center text-center p-8 sm:p-12 rounded-[12px] border border-dashed border-[var(--border)] bg-[var(--surface-2)]/40',
        className
      )}
    >
      <div className="w-12 h-12 rounded-full bg-[var(--surface-2)] border border-[var(--border)] flex items-center justify-center text-[var(--muted)] mb-3">
        <Icon className="w-6 h-6 stroke-[1.5]" />
      </div>
      <HeadingTag className="text-base font-semibold text-[var(--text)] mb-1">{title}</HeadingTag>
      {displayMessage && (
        <p className="text-xs text-[var(--muted)] max-w-sm mb-4 leading-relaxed">{displayMessage}</p>
      )}
      {action && <div>{action}</div>}
    </div>
  );
};

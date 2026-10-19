import React from 'react';
import { cn } from '../../lib/utils';

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'text' | 'statCard' | 'tableRow' | 'badge' | 'card';
}

export const Skeleton: React.FC<SkeletonProps> = ({
  className,
  variant = 'default',
  ...props
}) => {
  if (variant === 'statCard') {
    return (
      <div
        className={cn(
          'rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 space-y-3 animate-pulse',
          className
        )}
      >
        <div className="flex items-center justify-between">
          <div className="h-3.5 w-24 rounded-[6px] bg-[var(--surface-2)]" />
          <div className="h-8 w-8 rounded-[8px] bg-[var(--surface-2)]" />
        </div>
        <div className="h-8 w-32 rounded-[6px] bg-[var(--surface-2)]" />
        <div className="h-3 w-40 rounded-[6px] bg-[var(--surface-2)]" />
      </div>
    );
  }

  if (variant === 'tableRow') {
    return (
      <div className={cn('flex items-center gap-4 py-3 px-4 border-b border-[var(--border)] animate-pulse', className)}>
        <div className="h-4 w-1/4 rounded-[6px] bg-[var(--surface-2)]" />
        <div className="h-4 w-1/6 rounded-[6px] bg-[var(--surface-2)]" />
        <div className="h-4 w-1/6 rounded-[6px] bg-[var(--surface-2)]" />
        <div className="h-4 w-1/5 rounded-[6px] bg-[var(--surface-2)]" />
        <div className="h-6 w-16 rounded-[8px] bg-[var(--surface-2)] ml-auto" />
      </div>
    );
  }

  if (variant === 'badge') {
    return (
      <div
        className={cn(
          'inline-block h-5 w-16 rounded-[8px] bg-[var(--surface-2)] animate-pulse',
          className
        )}
        {...props}
      />
    );
  }

  if (variant === 'text') {
    return (
      <div
        className={cn('h-3.5 w-full rounded-[6px] bg-[var(--surface-2)] animate-pulse', className)}
        {...props}
      />
    );
  }

  return (
    <div
      className={cn('animate-pulse rounded-[8px] bg-[var(--surface-2)]', className)}
      {...props}
    />
  );
};

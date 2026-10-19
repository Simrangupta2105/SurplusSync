import React from 'react';

interface PageHeaderProps {
  title: string;
  description?: string;
  subtitle?: string;
  action?: React.ReactNode;
  badge?: React.ReactNode;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  description,
  subtitle,
  action,
  badge,
}) => {
  const desc = description || subtitle;
  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
      <div className="space-y-1">
        <div className="flex items-center gap-2.5">
          <h1 className="text-2xl sm:text-[28px] font-semibold text-[var(--text)] tracking-tight">
            {title}
          </h1>
          {badge}
        </div>
        {desc && (
          <p className="text-sm text-[var(--muted)] font-normal">
            {desc}
          </p>
        )}

      </div>
      {action && (
        <div className="flex items-center gap-2.5 shrink-0">
          {action}
        </div>
      )}
    </div>
  );
};

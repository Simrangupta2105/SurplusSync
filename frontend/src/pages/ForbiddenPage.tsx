import React from 'react';
import { ShieldAlert, Home } from 'lucide-react';
import { Button } from '../components/ui/Button';

interface ForbiddenPageProps {
  onGoHome: () => void;
  requiredRole?: string;
}

export const ForbiddenPage: React.FC<ForbiddenPageProps> = ({
  onGoHome,
  requiredRole = 'authorized personnel',
}) => {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
      <div className="w-16 h-16 rounded-full bg-[var(--color-danger-subtle)] text-[var(--color-danger)] border border-[var(--color-danger-border)] flex items-center justify-center mb-5 animate-in zoom-in-95">
        <ShieldAlert className="w-8 h-8" />
      </div>

      <span className="text-xs font-semibold uppercase tracking-wider text-[var(--color-danger)]">
        403 Access Denied
      </span>

      <h1 className="mt-2 text-2xl sm:text-3xl font-bold text-[var(--text)] tracking-tight">
        Restricted Area
      </h1>

      <p className="mt-2 text-sm text-[var(--muted)] max-w-md leading-relaxed">
        This section is reserved for {requiredRole}. Your current organization role does not have permission to view or manage these resources.
      </p>

      <div className="mt-6 flex items-center gap-3">
        <Button variant="primary" onClick={onGoHome} className="gap-2">
          <Home className="w-4 h-4" />
          <span>Return to Dashboard</span>
        </Button>
      </div>
    </div>
  );
};

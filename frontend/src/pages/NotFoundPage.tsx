import React from 'react';
import { FileQuestion, Home } from 'lucide-react';
import { Button } from '../components/ui/Button';

interface NotFoundPageProps {
  onGoHome: () => void;
}

export const NotFoundPage: React.FC<NotFoundPageProps> = ({ onGoHome }) => {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
      <div className="w-16 h-16 rounded-full bg-[var(--surface-2)] text-[var(--muted)] border border-[var(--border)] flex items-center justify-center mb-5 animate-in zoom-in-95">
        <FileQuestion className="w-8 h-8 text-[var(--primary)]" />
      </div>

      <span className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)] tabular-nums">
        404 Not Found
      </span>

      <h1 className="mt-2 text-2xl sm:text-3xl font-bold text-[var(--text)] tracking-tight">
        Page Does Not Exist
      </h1>

      <p className="mt-2 text-sm text-[var(--muted)] max-w-md leading-relaxed">
        The route or view you are attempting to access does not exist or may have been relocated.
      </p>

      <div className="mt-6">
        <Button variant="primary" onClick={onGoHome} className="gap-2">
          <Home className="w-4 h-4" />
          <span>Back to Dashboard</span>
        </Button>
      </div>
    </div>
  );
};

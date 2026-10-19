import React from 'react';
import { Lock, LogIn } from 'lucide-react';
import { Button } from './ui/Button';

interface SessionExpiredDialogProps {
  isOpen: boolean;
  onLogin: () => void;
}

export const SessionExpiredDialog: React.FC<SessionExpiredDialogProps> = ({
  isOpen,
  onLogin,
}) => {
  if (!isOpen) return null;

  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="session-expired-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs"
    >
      <div className="w-full max-w-sm rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl text-center space-y-4 animate-in zoom-in-95">
        <div className="mx-auto w-12 h-12 rounded-full bg-[var(--color-warning-subtle)] text-[var(--color-warning)] border border-[var(--color-warning-border)] flex items-center justify-center">
          <Lock className="w-6 h-6" />
        </div>

        <div className="space-y-1">
          <h2 id="session-expired-title" className="text-base font-semibold text-[var(--text)]">
            Session Expired
          </h2>
          <p className="text-xs text-[var(--muted)] leading-relaxed">
            Your security credentials have expired. Please sign in again to resume managing your food surplus data.
          </p>
        </div>

        <div className="pt-2">
          <Button
            variant="primary"
            size="sm"
            onClick={onLogin}
            className="w-full gap-2 justify-center"
          >
            <LogIn className="w-4 h-4" />
            <span>Sign In Again</span>
          </Button>
        </div>
      </div>
    </div>
  );
};

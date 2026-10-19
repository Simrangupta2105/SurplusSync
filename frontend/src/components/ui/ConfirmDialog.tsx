import React, { useEffect, useRef } from 'react';
import { AlertTriangle, Info, X } from 'lucide-react';
import { Button } from './Button';
import { cn } from '../../lib/utils';

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'danger' | 'primary' | 'warning';
  onConfirm: () => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'primary',
  onConfirm,
  onCancel,
  isLoading = false,
}) => {
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelBtnRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onCancel();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    // Autofocus safe cancel button
    setTimeout(() => cancelBtnRef.current?.focus(), 50);

    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onCancel]);

  if (!isOpen) return null;

  const iconVariants = {
    danger: <AlertTriangle className="w-5 h-5 text-[var(--color-danger)] shrink-0" />,
    warning: <AlertTriangle className="w-5 h-5 text-[var(--color-warning)] shrink-0" />,
    primary: <Info className="w-5 h-5 text-[var(--primary)] shrink-0" />,
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      aria-describedby="confirm-dialog-desc"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity animate-in fade-in duration-200"
        onClick={onCancel}
      />

      {/* Dialog Card */}
      <div
        ref={dialogRef}
        className={cn(
          'relative w-full max-w-md rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl transition-all duration-200 animate-in zoom-in-95',
          'focus:outline-none'
        )}
      >
        <div className="flex items-start gap-4">
          <div className="rounded-full bg-[var(--surface-2)] p-2.5 border border-[var(--border)]">
            {iconVariants[variant]}
          </div>

          <div className="flex-1 min-w-0">
            <h3 id="confirm-dialog-title" className="text-base font-semibold text-[var(--text)]">
              {title}
            </h3>
            <p id="confirm-dialog-desc" className="mt-1.5 text-sm text-[var(--muted)] leading-relaxed">
              {description}
            </p>
          </div>

          <button
            onClick={onCancel}
            aria-label="Close dialog"
            className="rounded-[8px] p-1 text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="mt-6 flex items-center justify-end gap-3">
          <Button
            ref={cancelBtnRef}
            variant="outline"
            size="sm"
            onClick={onCancel}
            disabled={isLoading}
          >
            {cancelLabel}
          </Button>

          <Button
            variant={variant === 'danger' ? 'danger' : 'primary'}
            size="sm"
            onClick={onConfirm}
            isLoading={isLoading}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
};

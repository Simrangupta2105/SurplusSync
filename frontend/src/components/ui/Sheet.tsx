import React, { useEffect } from 'react';
import { X } from 'lucide-react';
import { cn } from '../../lib/utils';

interface SheetProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  width?: 'sm' | 'md' | 'lg' | 'xl';
}

export const Sheet: React.FC<SheetProps> = ({
  isOpen,
  onClose,
  title,
  description,
  children,
  footer,
  width = 'md',
}) => {
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };

    window.addEventListener('keydown', handleKeyDown);
    // Prevent body background scroll while sheet is open
    document.body.style.overflow = 'hidden';

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const widthClasses = {
    sm: 'sm:max-w-md',
    md: 'sm:max-w-lg',
    lg: 'sm:max-w-xl',
    xl: 'sm:max-w-2xl',
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex justify-end"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity animate-in fade-in duration-200"
        onClick={onClose}
      />

      {/* Drawer Container: Full screen on mobile (<640px), right slide-over on >=sm */}
      <div
        className={cn(
          'relative z-10 flex h-full w-full flex-col bg-[var(--surface)] text-[var(--text)] border-l border-[var(--border)] shadow-2xl transition-transform duration-200 ease-in-out animate-in slide-in-from-right',
          widthClasses[width]
        )}
      >
        {/* Sheet Header */}
        <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-4">
          <div className="min-w-0 pr-4">
            <h2 className="text-base font-semibold text-[var(--text)] tracking-tight">
              {title}
            </h2>
            {description && (
              <p className="mt-0.5 text-xs text-[var(--muted)] truncate">
                {description}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close sheet"
            className="rounded-[8px] p-1.5 text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Sheet Scrollable Body */}
        <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-4">
          {children}
        </div>

        {/* Sheet Footer */}
        {footer && (
          <div className="border-t border-[var(--border)] bg-[var(--surface-2)] px-5 py-3.5 flex items-center justify-end gap-3 shrink-0">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
};

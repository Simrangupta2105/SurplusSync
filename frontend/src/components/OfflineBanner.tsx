import React, { useState, useEffect } from 'react';
import { WifiOff, RefreshCw } from 'lucide-react';

export const OfflineBanner: React.FC = () => {
  const [isOffline, setIsOffline] = useState(!navigator.onLine);

  useEffect(() => {
    const handleOnline = () => setIsOffline(false);
    const handleOffline = () => setIsOffline(true);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  if (!isOffline) return null;

  return (
    <aside
      aria-label="Offline status banner"
      className="sticky top-0 z-50 w-full bg-[var(--color-danger-subtle)] border-b border-[var(--color-danger-border)] px-4 py-2 text-xs text-[var(--color-danger)] font-medium flex items-center justify-between shadow-xs transition-all animate-in slide-in-from-top"
    >
      <div className="flex items-center gap-2 max-w-7xl mx-auto w-full">
        <WifiOff className="w-4 h-4 shrink-0" />
        <span className="flex-1">
          You are currently offline. Changes will automatically synchronize when connection is restored.
        </span>
        <button
          onClick={() => window.location.reload()}
          className="flex items-center gap-1 font-semibold underline underline-offset-2 hover:opacity-80 cursor-pointer ml-2"
        >
          <RefreshCw className="w-3 h-3" />
          <span>Retry</span>
        </button>
      </div>
    </aside>
  );
};

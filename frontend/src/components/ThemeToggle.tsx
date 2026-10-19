import React, { useEffect, useState } from 'react';
import { Sun, Moon } from 'lucide-react';
import { cn } from '../lib/utils';

interface ThemeToggleProps {
  className?: string;
  showLabel?: boolean;
}

export const ThemeToggle: React.FC<ThemeToggleProps> = ({ className, showLabel = false }) => {
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    const saved = localStorage.getItem('surplussync_theme');
    if (saved === 'dark' || saved === 'light') return saved;
    // Dark is default; fallback to matchMedia if available
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches
      ? 'light'
      : 'dark';
  });

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
      root.classList.remove('light');
    } else {
      root.classList.add('light');
      root.classList.remove('dark');
    }
    localStorage.setItem('surplussync_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  return (
    <button
      onClick={toggleTheme}
      id="theme-toggle-btn"
      type="button"
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2 text-xs font-medium text-[var(--text)] transition-colors duration-150 hover:border-[var(--primary)] hover:bg-[var(--surface)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] cursor-pointer select-none',
        className
      )}
      title={theme === 'dark' ? 'Switch to warm light theme' : 'Switch to dark theme'}
      aria-label={`Current theme is ${theme}. Click to toggle.`}
    >
      {theme === 'dark' ? (
        <Sun className="h-4 w-4 text-[var(--accent)] transition-transform duration-200 hover:rotate-45" />
      ) : (
        <Moon className="h-4 w-4 text-[var(--primary)] transition-transform duration-200 hover:-rotate-12" />
      )}
      {showLabel && (
        <span className="capitalize">{theme === 'dark' ? 'Dark' : 'Warm Light'}</span>
      )}
    </button>
  );
};

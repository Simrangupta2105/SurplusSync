import React, { useState, useRef, useEffect } from 'react';
import {
  Menu,
  Search,
  Bell,
  LogOut,
  ChevronDown,
  Building2,
  Users,
  Clock,
  Star,
  Settings,
  Shield,
  Database,
  ArrowRightLeft,
} from 'lucide-react';
import { ThemeToggle } from './ThemeToggle';
import { cn } from '../lib/utils';
import type { OrganizationType, NotificationItem } from '../types';

interface HeaderProps {
  onToggleSidebar: () => void;
  pageTitle: string;
  onOpenCommandPalette: () => void;
  isSidebarCollapsed?: boolean;
  orgType?: OrganizationType;
  orgName?: string;
  userName?: string;
  isVerified?: boolean;
  isDemoMode?: boolean;
  isPlatformAdmin?: boolean;
  notifications?: NotificationItem[];
  onMarkNotificationRead?: (id: string) => void;
  onLogout: () => void;
  onSwitchPersona?: (persona: 'BUSINESS' | 'NGO' | 'NGO_UNVERIFIED' | 'ADMIN') => void;
  onNavigate?: (path: string) => void;
  onToggleDataMode?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  onToggleSidebar,
  pageTitle,
  onOpenCommandPalette,
  isSidebarCollapsed = false,
  orgType = 'BUSINESS',
  orgName = '',
  userName = '',
  isVerified = true,
  isDemoMode = false,
  isPlatformAdmin = false,
  notifications = [],
  onMarkNotificationRead,
  onLogout,
  onSwitchPersona,
  onNavigate,
  onToggleDataMode,
}) => {

  const [isNotifOpen, setIsNotifOpen] = useState(false);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const notifRef = useRef<HTMLDivElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  // Close menus on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setIsNotifOpen(false);
      }
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setIsUserMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <header
      className={cn(
        'fixed top-0 right-0 h-16 z-30 bg-[var(--surface)]/90 backdrop-blur-md border-b border-[var(--border)] transition-all duration-200 px-4 sm:px-6 flex items-center justify-between gap-3',
        isSidebarCollapsed ? 'left-0 lg:left-[72px]' : 'left-0 lg:left-[240px]'
      )}
    >
      {/* Left Section: Mobile Hamburger & Page Title / Breadcrumb */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onToggleSidebar}
          aria-label="Open sidebar navigation"
          className="lg:hidden p-2 rounded-[8px] text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors cursor-pointer"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)] hidden sm:inline-block">
            {orgType === 'NGO' ? 'NGO' : 'Business'}
          </span>
          <span className="text-[var(--border)] hidden sm:inline-block">/</span>
          <h1 className="text-sm sm:text-base font-bold text-[var(--text)] tracking-tight truncate">
            {pageTitle}
          </h1>
        </div>

        {/* Demo Mode Badge */}
        {isDemoMode && (
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-[var(--color-warning-subtle)] text-[var(--color-warning)] border border-[var(--color-warning-border)] shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-warning)] animate-pulse" />
            <span>Demo data</span>
          </div>
        )}
      </div>

      {/* Middle & Right Section: Command Palette (Ctrl+K), Notifications, Theme, User Menu */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        {/* Command Palette Button */}
        <button
          type="button"
          onClick={onOpenCommandPalette}
          className="flex items-center gap-2 rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] px-2.5 py-1.5 text-xs text-[var(--muted)] hover:text-[var(--text)] hover:border-[var(--primary)] transition-all cursor-pointer"
          title="Search anything (Ctrl+K)"
          aria-label="Search command palette"
        >
          <Search className="w-3.5 h-3.5" />
          <span className="hidden md:inline">Quick search...</span>
          <kbd className="hidden sm:inline-block rounded-[4px] border border-[var(--border)] bg-[var(--surface)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--muted)] shadow-2xs">
            ⌘K
          </kbd>
        </button>

        {/* Data Source Mode Switcher Pill */}
        {onToggleDataMode && (
          <button
            type="button"
            onClick={onToggleDataMode}
            title={isDemoMode ? "Currently in Demo Sandbox. Click to switch to Live Backend (Django DB on port 8000)" : "Currently in Live Backend Mode (connected to Django on port 8000). Click to switch to Demo Sandbox"}
            className={cn(
              "hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border transition-all cursor-pointer",
              isDemoMode
                ? "bg-[var(--surface-2)] border-[var(--border)] text-[var(--muted)] hover:border-[var(--primary)] hover:text-[var(--text)]"
                : "bg-[var(--color-success-subtle)] border-[var(--color-success-border)] text-[var(--color-success)] shadow-2xs"
            )}
          >
            <Database className="w-3 h-3 text-[var(--primary)]" />
            <span>{isDemoMode ? 'Demo Sandbox' : 'Live DB (8000)'}</span>
            <ArrowRightLeft className="w-2.5 h-2.5 opacity-60 ml-0.5" />
          </button>
        )}

        {/* Theme Toggle */}
        <ThemeToggle />

        {/* Notification Bell with Dropdown */}
        <div ref={notifRef} className="relative">
          <button
            type="button"
            onClick={() => setIsNotifOpen((prev) => !prev)}
            className="relative p-2 rounded-[8px] text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors cursor-pointer"
            aria-label={`Notifications (${unreadCount} unread)`}
          >
            <Bell className="w-4 h-4" />
            {unreadCount > 0 && (
              <span className="absolute top-1.5 right-1.5 flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--color-danger)] opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-[var(--color-danger)]" />
              </span>
            )}
          </button>

          {/* Notifications Dropdown Popover */}
          {isNotifOpen && (
            <div className="absolute right-0 mt-2 w-80 sm:w-96 rounded-[12px] border border-[var(--border)] bg-[var(--surface)] shadow-2xl z-50 overflow-hidden animate-in zoom-in-95 duration-150">
              <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)] bg-[var(--surface-2)]">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-[var(--text)]">Notifications</span>
                  {unreadCount > 0 && (
                    <span className="px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-[var(--color-danger-subtle)] text-[var(--color-danger)] tabular-nums">
                      {unreadCount} new
                    </span>
                  )}
                </div>
                <span className="text-[11px] text-[var(--muted)]">Real-time alerts</span>
              </div>

              <div className="max-h-72 overflow-y-auto divide-y divide-[var(--border)]">
                {notifications.length === 0 ? (
                  <div className="py-6 text-center text-xs text-[var(--muted)]">
                    No active notifications
                  </div>
                ) : (
                  notifications.map((notif) => (
                    <div
                      key={notif.id}
                      onClick={() => onMarkNotificationRead && onMarkNotificationRead(notif.id)}
                      className={cn(
                        'p-3.5 text-xs transition-colors cursor-pointer',
                        notif.is_read ? 'opacity-65 hover:opacity-100 hover:bg-[var(--surface-2)]' : 'bg-[var(--surface-2)]/40 hover:bg-[var(--surface-2)]'
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="font-semibold text-[var(--text)] truncate">
                          {notif.title}
                        </p>
                        {!notif.is_read && (
                          <span className="h-1.5 w-1.5 rounded-full bg-[var(--primary)] shrink-0 mt-1" />
                        )}
                      </div>
                      <p className="mt-1 text-[11px] text-[var(--muted)] leading-relaxed">
                        {notif.message}
                      </p>
                      <p className="mt-1.5 text-[10px] text-[var(--muted)] opacity-75 tabular-nums">
                        {new Date(notif.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* User Menu */}
        <div ref={userMenuRef} className="relative">
          <button
            type="button"
            onClick={() => setIsUserMenuOpen((prev) => !prev)}
            className="flex items-center gap-2 p-1.5 sm:px-2 rounded-[8px] hover:bg-[var(--surface-2)] transition-colors cursor-pointer"
            aria-label="User account menu"
          >
            <div className="w-7 h-7 rounded-full bg-[var(--primary)] text-white text-xs font-bold flex items-center justify-center shrink-0">
              {userName ? userName.charAt(0).toUpperCase() : 'U'}
            </div>
            <div className="hidden md:flex flex-col text-left min-w-0">
              <span className="text-xs font-semibold text-[var(--text)] leading-tight truncate">
                {userName || 'User'}
              </span>
              <span className="text-[10px] text-[var(--muted)] leading-tight truncate">
                {isPlatformAdmin
                  ? 'Platform Administrator'
                  : isVerified
                  ? 'Verified Partner'
                  : 'Verification Pending'}
              </span>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-[var(--muted)] hidden md:block" />
          </button>

          {/* User Menu Dropdown */}
          {isUserMenuOpen && (
            <div className="absolute right-0 mt-2 w-64 rounded-[12px] border border-[var(--border)] bg-[var(--surface)] shadow-2xl z-50 overflow-hidden animate-in zoom-in-95 duration-150">
              {/* Profile Overview */}
              <div className="p-3.5 border-b border-[var(--border)] bg-[var(--surface-2)]">
                <p className="text-xs font-bold text-[var(--text)] truncate">{userName}</p>
                <p className="text-[11px] text-[var(--muted)] truncate">
                  {isPlatformAdmin ? 'SurplusSync Platform' : orgName}
                </p>
                <div className="mt-2 flex items-center gap-1.5">
                  <span
                    className={cn(
                      'px-2 py-0.5 rounded-[6px] text-[10px] font-semibold border',
                      isPlatformAdmin
                        ? 'bg-[var(--primary)]/15 text-[var(--primary)] border-[var(--primary)]/30'
                        : isVerified
                        ? 'bg-[var(--color-success-subtle)] text-[var(--color-success)] border-[var(--color-success-border)]'
                        : 'bg-[var(--color-warning-subtle)] text-[var(--color-warning)] border-[var(--color-warning-border)]'
                    )}
                  >
                    {isPlatformAdmin ? 'Platform Staff' : isVerified ? 'Verified' : 'Pending Review'}
                  </span>
                  {!isPlatformAdmin && (
                    <span className="text-[10px] text-[var(--muted)] font-medium">({orgType})</span>
                  )}
                </div>
              </div>

              {/* Data Mode Toggle Option */}
              {onToggleDataMode && (
                <div className="p-2 border-b border-[var(--border)] bg-[var(--surface-2)]/40">
                  <div className="flex items-center justify-between px-2 py-0.5 mb-1.5">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]">
                      Backend Mode
                    </span>
                    <span className={cn(
                      "text-[9px] font-mono px-1.5 py-0.5 rounded font-semibold",
                      isDemoMode ? "bg-[var(--surface-2)] text-[var(--muted)] border border-[var(--border)]" : "bg-[var(--color-success-subtle)] text-[var(--color-success)]"
                    )}>
                      {isDemoMode ? 'Sandbox' : 'Live DB'}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      onToggleDataMode();
                      setIsUserMenuOpen(false);
                    }}
                    className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-[6px] text-xs font-medium text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors border border-[var(--border)] cursor-pointer"
                  >
                    <span className="flex items-center gap-1.5 truncate">
                      <Database className="w-3.5 h-3.5 text-[var(--primary)] shrink-0" />
                      <span className="truncate">{isDemoMode ? 'Switch to Live Backend' : 'Switch to Demo Sandbox'}</span>
                    </span>
                    <ArrowRightLeft className="w-3 h-3 text-[var(--muted)] shrink-0 ml-1" />
                  </button>
                </div>
              )}

              {/* Demo Persona Switcher (Only in demo mode) */}
              {isDemoMode && onSwitchPersona && (
                <div className="p-2 border-b border-[var(--border)]">
                  <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]">
                    Switch Demo Persona
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      onSwitchPersona('BUSINESS');
                      setIsUserMenuOpen(false);
                    }}
                    className={cn(
                      'w-full flex items-center gap-2 px-2.5 py-1.5 rounded-[6px] text-xs text-left cursor-pointer transition-colors',
                      !isPlatformAdmin && orgType === 'BUSINESS'
                        ? 'bg-[var(--primary)] text-white font-medium'
                        : 'text-[var(--text)] hover:bg-[var(--surface-2)]'
                    )}
                  >
                    <Building2 className="w-3.5 h-3.5 shrink-0" />
                    <span className="truncate">Business (Partner Kitchen)</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      onSwitchPersona('NGO');
                      setIsUserMenuOpen(false);
                    }}
                    className={cn(
                      'w-full flex items-center gap-2 px-2.5 py-1.5 rounded-[6px] text-xs text-left cursor-pointer transition-colors mt-0.5',
                      !isPlatformAdmin && orgType === 'NGO' && isVerified
                        ? 'bg-[var(--primary)] text-white font-medium'
                        : 'text-[var(--text)] hover:bg-[var(--surface-2)]'
                    )}
                  >
                    <Users className="w-3.5 h-3.5 shrink-0" />
                    <span className="truncate">NGO (Relief Foundation)</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      onSwitchPersona('NGO_UNVERIFIED');
                      setIsUserMenuOpen(false);
                    }}
                    className={cn(
                      'w-full flex items-center gap-2 px-2.5 py-1.5 rounded-[6px] text-xs text-left cursor-pointer transition-colors mt-0.5',
                      !isPlatformAdmin && orgType === 'NGO' && !isVerified
                        ? 'bg-[var(--primary)] text-white font-medium'
                        : 'text-[var(--text)] hover:bg-[var(--surface-2)]'
                    )}
                  >
                    <Clock className="w-3.5 h-3.5 shrink-0 text-[var(--color-warning)]" />
                    <span className="truncate">Unverified NGO (Review)</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      onSwitchPersona('ADMIN');
                      setIsUserMenuOpen(false);
                    }}
                    className={cn(
                      'w-full flex items-center gap-2 px-2.5 py-1.5 rounded-[6px] text-xs text-left cursor-pointer transition-colors mt-0.5',
                      isPlatformAdmin
                        ? 'bg-[var(--primary)] text-white font-medium'
                        : 'text-[var(--text)] hover:bg-[var(--surface-2)]'
                    )}
                  >
                    <Shield className="w-3.5 h-3.5 shrink-0 text-[var(--primary)]" />
                    <span className="truncate">Platform Admin (Superuser)</span>
                  </button>
                </div>
              )}

              {/* Profile / Settings Navigation Link */}
              {onNavigate && (
                <div className="p-1.5 border-b border-[var(--border)]">
                  <button
                    type="button"
                    onClick={() => {
                      setIsUserMenuOpen(false);
                      if (isPlatformAdmin) {
                        onNavigate('admin/settings');
                      } else {
                        onNavigate(orgType === 'NGO' ? 'profile' : 'settings');
                      }
                    }}
                    className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-[6px] text-xs font-medium text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors cursor-pointer text-left"
                  >
                    {isPlatformAdmin ? (
                      <>
                        <Shield className="w-3.5 h-3.5 text-[var(--primary)] shrink-0" />
                        <span>Platform Settings</span>
                      </>
                    ) : orgType === 'NGO' ? (
                      <>
                        <Star className="w-3.5 h-3.5 text-[var(--primary)] shrink-0" />
                        <span>Profile &amp; Ratings</span>
                      </>
                    ) : (
                      <>
                        <Settings className="w-3.5 h-3.5 text-[var(--primary)] shrink-0" />
                        <span>Facility Settings</span>
                      </>
                    )}
                  </button>
                </div>
              )}


              {/* Sign Out */}
              <div className="p-1.5">
                <button
                  type="button"
                  onClick={() => {
                    setIsUserMenuOpen(false);
                    onLogout();
                  }}
                  className="w-full flex items-center gap-2 px-2.5 py-2 rounded-[6px] text-xs font-medium text-[var(--color-danger)] hover:bg-[var(--color-danger-subtle)] transition-colors cursor-pointer"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  <span>Sign Out</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
